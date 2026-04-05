<?php

if (!defined('ABSPATH')) {
    exit;
}

class VX_Site_Importer
{
    public function import_from_file($path)
    {
        if (!file_exists($path)) {
            return new WP_Error('vx_site_missing_file', sprintf('Import file not found: %s', $path));
        }

        $raw = file_get_contents($path);
        $data = json_decode($raw, true);

        if (!is_array($data)) {
            return new WP_Error('vx_site_invalid_json', 'Import file does not contain valid JSON.');
        }

        $category_map = $this->import_categories($data['categories'] ?? array());
        $post_map = $this->import_posts($data['posts'] ?? array(), $category_map);
        $page_map = $this->import_pages($data['pages'] ?? array(), $category_map, $post_map);

        $this->import_navigation($data['navigation'] ?? array(), $page_map);
        update_option('vx_site_imported_site_texts', $data['site_texts'] ?? array(), false);
        update_option('vx_site_imported_post_types', $data['post_types'] ?? array(), false);

        return array(
            'message' => sprintf(
                'Imported %d categories, %d posts, and %d pages.',
                count($category_map),
                count($post_map),
                count($page_map)
            ),
        );
    }

    private function import_categories($categories)
    {
        $map = array();

        foreach ($categories as $category) {
            $term = term_exists($category['slug'], 'category');
            if (!$term) {
                $term = wp_insert_term(
                    $category['title'],
                    'category',
                    array('slug' => $category['slug'])
                );
            } else {
                wp_update_term((int) $term['term_id'], 'category', array('name' => $category['title']));
            }

            if (!is_wp_error($term)) {
                $term_id = is_array($term) ? (int) $term['term_id'] : (int) $term;
                $map[$category['slug']] = $term_id;
            }
        }

        return $map;
    }

    private function import_posts($posts, $category_map)
    {
        $map = array();

        foreach ($posts as $post) {
            $existing = get_page_by_path($post['slug'], OBJECT, 'post');
            $postarr = array(
                'ID' => $existing ? $existing->ID : 0,
                'post_type' => 'post',
                'post_title' => $post['title'],
                'post_name' => $post['slug'],
                'post_excerpt' => $post['summary'] ?? '',
                'post_content' => $post['rendered_html'] ?: ($post['fallback_html'] ?? ''),
                'post_status' => $post['status'] ?? 'draft',
                'post_date' => $post['published_at'] ?: current_time('mysql'),
            );

            $post_id = wp_insert_post(wp_slash($postarr), true);
            if (is_wp_error($post_id)) {
                continue;
            }

            $category_ids = array();
            foreach (($post['categories'] ?? array()) as $slug) {
                if (isset($category_map[$slug])) {
                    $category_ids[] = $category_map[$slug];
                }
            }
            if (!empty($category_ids)) {
                wp_set_post_terms($post_id, $category_ids, 'category', false);
            }

            update_post_meta($post_id, 'vx_legacy_post_type', sanitize_text_field($post['legacy_post_type'] ?? ''));
            update_post_meta($post_id, 'vx_source_slug', sanitize_text_field($post['slug']));
            $map[$post['slug']] = (int) $post_id;
        }

        return $map;
    }

    private function import_pages($pages, $category_map, $post_map)
    {
        $map = array();
        $front_page_id = 0;

        foreach ($pages as $page) {
            $existing = get_page_by_path($page['slug'], OBJECT, 'page');
            $postarr = array(
                'ID' => $existing ? $existing->ID : 0,
                'post_type' => 'page',
                'post_title' => $page['title'],
                'post_name' => $page['slug'],
                'post_excerpt' => $page['summary'] ?? '',
                'post_content' => $page['rendered_html'] ?: ($page['fallback_html'] ?? ''),
                'post_status' => $page['status'] ?? 'draft',
            );

            $page_id = wp_insert_post(wp_slash($postarr), true);
            if (is_wp_error($page_id)) {
                continue;
            }

            $path = vx_site_normalize_path($page['path'] ?? '/');
            update_post_meta($page_id, 'vx_page_path', $path);
            update_post_meta($page_id, 'vx_posts_enabled', !empty($page['feed']['enabled']));
            update_post_meta($page_id, 'vx_posts_limit', absint($page['feed']['limit'] ?? 12));

            $category_filters = array();
            foreach (($page['feed']['category_filters'] ?? array()) as $slug) {
                if (isset($category_map[$slug])) {
                    $category_filters[] = $category_map[$slug];
                }
            }
            update_post_meta($page_id, 'vx_category_filters', $category_filters);

            $manual_post_ids = array();
            foreach (($page['feed']['manual_post_slugs'] ?? array()) as $slug) {
                if (isset($post_map[$slug])) {
                    $manual_post_ids[] = $post_map[$slug];
                }
            }
            update_post_meta($page_id, 'vx_manual_post_ids', $manual_post_ids);

            $feed_source = $page['feed']['source'] ?? 'all';
            $legacy_post_types = array_values(array_filter($page['feed']['legacy_post_type_filters'] ?? array()));
            if ($feed_source === 'manual') {
                update_post_meta($page_id, 'vx_posts_source', 'manual');
            } elseif (!empty($category_filters)) {
                update_post_meta($page_id, 'vx_posts_source', 'filtered');
            } else {
                update_post_meta($page_id, 'vx_posts_source', 'all');
            }
            update_post_meta($page_id, 'vx_legacy_post_type_filters', $legacy_post_types);
            update_post_meta($page_id, 'vx_feed_title', sanitize_text_field($page['feed']['title'] ?? ''));

            if (!empty($page['is_homepage'])) {
                $front_page_id = (int) $page_id;
            }

            $map[$path] = (int) $page_id;
        }

        if ($front_page_id) {
            update_option('show_on_front', 'page');
            update_option('page_on_front', $front_page_id);
        }

        return $map;
    }

    private function import_navigation($navigation, $page_map)
    {
        if (empty($navigation)) {
            return;
        }

        $menu_name = 'Primary Navigation';
        $menu = wp_get_nav_menu_object($menu_name);
        $menu_id = $menu ? (int) $menu->term_id : (int) wp_create_nav_menu($menu_name);

        foreach ($navigation as $item) {
            $path = vx_site_normalize_path($item['path'] ?? '/');
            if (empty($page_map[$path])) {
                continue;
            }

            $existing_item = $this->find_menu_item($menu_id, $page_map[$path]);
            if ($existing_item) {
                wp_update_nav_menu_item($menu_id, $existing_item, array(
                    'menu-item-title' => $item['title'],
                    'menu-item-object-id' => $page_map[$path],
                    'menu-item-object' => 'page',
                    'menu-item-type' => 'post_type',
                    'menu-item-status' => 'publish',
                ));
                continue;
            }

            wp_update_nav_menu_item($menu_id, 0, array(
                'menu-item-title' => $item['title'],
                'menu-item-object-id' => $page_map[$path],
                'menu-item-object' => 'page',
                'menu-item-type' => 'post_type',
                'menu-item-status' => 'publish',
            ));
        }

        $locations = get_theme_mod('nav_menu_locations', array());
        if (isset($locations['primary'])) {
            $locations['primary'] = $menu_id;
        } elseif (isset($locations['main-menu'])) {
            $locations['main-menu'] = $menu_id;
        } elseif (!empty($locations)) {
            $keys = array_keys($locations);
            $locations[$keys[0]] = $menu_id;
        }

        if (!empty($locations)) {
            set_theme_mod('nav_menu_locations', $locations);
        }
    }

    private function find_menu_item($menu_id, $object_id)
    {
        $items = wp_get_nav_menu_items($menu_id);
        if (empty($items)) {
            return 0;
        }

        foreach ($items as $item) {
            if ((int) $item->object_id === (int) $object_id) {
                return (int) $item->ID;
            }
        }

        return 0;
    }
}
