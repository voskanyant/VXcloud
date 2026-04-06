<?php
/**
 * Plugin Name: VX Site Integration
 * Description: WordPress integration layer for the VXcloud public-site migration.
 * Version: 0.2.12
 * Author: OpenAI Codex
 */

if (!defined('ABSPATH')) {
    exit;
}

define('VX_SITE_INTEGRATION_VERSION', '0.2.12');
define('VX_SITE_INTEGRATION_DIR', plugin_dir_path(__FILE__));
define('VX_SITE_INTEGRATION_URL', plugin_dir_url(__FILE__));
define('VX_SITE_SHELL_MARKER', '<!--VX_SITE_SHELL_CONTENT-->');

require_once VX_SITE_INTEGRATION_DIR . 'includes/class-vx-site-importer.php';

function vx_site_default_options() {
    return array(
        'cta_label' => 'Open account',
        'price_label' => '',
        'django_account_url' => '/account/',
        'django_open_app_url' => '/open-app/',
    );
}

function vx_site_get_options() {
    return wp_parse_args(get_option('vx_site_options', array()), vx_site_default_options());
}

function vx_site_build_shell_url($path) {
    $path = trim((string) $path);
    if ($path === '') {
        return home_url('/');
    }
    if (preg_match('#^https?://#i', $path)) {
        return esc_url_raw($path);
    }
    return home_url('/' . ltrim($path, '/'));
}

function vx_site_normalize_shell_path($url) {
    $url = trim((string) $url);
    if ($url === '') {
        return '';
    }

    $parts = wp_parse_url($url);
    if (!$parts) {
        return '';
    }

    $path = isset($parts['path']) ? $parts['path'] : '';
    $query = isset($parts['query']) && $parts['query'] !== '' ? '?' . $parts['query'] : '';
    return $path . $query;
}

function vx_site_pick_menu_location($preferred) {
    $locations = get_nav_menu_locations();
    if (empty($locations) || !is_array($locations)) {
        return 0;
    }

    foreach ($preferred as $location_name) {
        if (!empty($locations[$location_name])) {
            return (int) $locations[$location_name];
        }
    }

    $first_menu_id = reset($locations);
    return $first_menu_id ? (int) $first_menu_id : 0;
}

function vx_site_build_menu_items($menu_id) {
    if (!$menu_id) {
        return array();
    }

    $items = wp_get_nav_menu_items($menu_id);
    if (!is_array($items)) {
        return array();
    }

    $menu = array();
    foreach ($items as $item) {
        if ((int) $item->menu_item_parent !== 0) {
            continue;
        }

        $url = isset($item->url) ? (string) $item->url : '';
        $menu[] = array(
            'label' => wp_strip_all_tags($item->title ?: ''),
            'url' => esc_url_raw($url),
            'path' => vx_site_normalize_shell_path($url),
        );
    }

    return $menu;
}

function vx_site_build_shell_payload() {
    $options = vx_site_get_options();
    $site_name = get_bloginfo('name') ?: 'VXcloud';
    $site_description = get_bloginfo('description') ?: 'Стабильный VPN/прокси для повседневного доступа к интернету.';

    $header_menu_id = vx_site_pick_menu_location(array('primary', 'main-menu', 'main_menu', 'header', 'desktop'));
    $footer_menu_id = vx_site_pick_menu_location(array('footer', 'footer-1', 'footer_menu', 'footer-menu', 'secondary'));

    $payload = array(
        'brand' => array(
            'label' => $site_name,
            'url' => home_url('/'),
        ),
        'header_menu' => vx_site_build_menu_items($header_menu_id),
        'footer_menu' => vx_site_build_menu_items($footer_menu_id),
        'cta' => array(
            'label' => (string) $options['cta_label'],
            'price_label' => (string) $options['price_label'],
            'account_url' => vx_site_build_shell_url((string) $options['django_account_url']),
            'buy_url' => vx_site_build_shell_url(trailingslashit((string) $options['django_account_url']) . 'buy/'),
            'open_app_url' => vx_site_build_shell_url((string) $options['django_open_app_url']),
        ),
        'footer' => array(
            'copy' => '© ' . $site_name,
            'tagline' => $site_description,
        ),
    );

    $fragments = vx_site_build_shell_fragments_payload();
    if (!empty($fragments)) {
        $payload['fragments'] = $fragments;
    }

    return $payload;
}

function vx_site_shell_placeholder_shortcode() {
    return VX_SITE_SHELL_MARKER;
}
add_shortcode('vx_shell_placeholder', 'vx_site_shell_placeholder_shortcode');

function vx_site_get_shell_bridge_page() {
    $page = get_page_by_path('vx-shell-bridge', OBJECT, 'page');
    if ($page instanceof WP_Post) {
        return $page;
    }

    $page_id = wp_insert_post(array(
        'post_type' => 'page',
        'post_status' => 'publish',
        'post_title' => 'VX Shell Bridge',
        'post_name' => 'vx-shell-bridge',
        'post_content' => '[vx_shell_placeholder]',
        'comment_status' => 'closed',
        'ping_status' => 'closed',
    ), true);

    if (is_wp_error($page_id) || !$page_id) {
        return null;
    }

    update_post_meta((int) $page_id, 'vx_page_path', '/vx-shell-bridge/');
    $page = get_post((int) $page_id);
    return $page instanceof WP_Post ? $page : null;
}

function vx_site_get_account_host_page() {
    $page = get_page_by_path('account', OBJECT, 'page');
    if ($page instanceof WP_Post) {
        if (strpos((string) $page->post_content, '[vx_account_app]') === false) {
            wp_update_post(array(
                'ID' => (int) $page->ID,
                'post_content' => '[vx_account_app]',
            ));
            $page = get_post((int) $page->ID);
        }
        return $page instanceof WP_Post ? $page : null;
    }

    $page_id = wp_insert_post(array(
        'post_type' => 'page',
        'post_status' => 'publish',
        'post_title' => 'Мой аккаунт',
        'post_name' => 'account',
        'post_content' => '[vx_account_app]',
        'comment_status' => 'closed',
        'ping_status' => 'closed',
    ), true);

    if (is_wp_error($page_id) || !$page_id) {
        return null;
    }

    return get_post((int) $page_id);
}

function vx_site_extract_shell_fragments_from_html($html) {
    $html = (string) $html;
    if ($html === '' || strpos($html, VX_SITE_SHELL_MARKER) === false) {
        return array();
    }

    if (!preg_match('/<body\b[^>]*class=(["\'])(.*?)\1[^>]*>([\s\S]*?)<\/body>/i', $html, $body_match)) {
        return array();
    }

    $head_html = '';
    if (preg_match('/<head\b[^>]*>([\s\S]*?)<\/head>/i', $html, $head_match)) {
        $head_html = $head_match[1];
    }

    $parts = explode(VX_SITE_SHELL_MARKER, $body_match[3], 2);
    if (count($parts) !== 2) {
        return array();
    }

    preg_match_all('/<link\b[^>]*rel=(["\'])[^"\']*stylesheet[^"\']*\1[^>]*href=(["\'])(.*?)\2/i', $head_html, $stylesheet_matches, PREG_SET_ORDER);
    preg_match_all('/(<style\b[\s\S]*?<\/style>)/i', $head_html, $style_matches);
    preg_match_all('/<script\b[^>]*src=(["\'])(.*?)\1/i', $head_html, $script_matches, PREG_SET_ORDER);

    $stylesheets = array();
    foreach ($stylesheet_matches as $match) {
        $stylesheets[] = $match[3];
    }

    $scripts = array();
    foreach ($script_matches as $match) {
        if (strpos($match[2], '/wp-content/') !== false || strpos($match[2], '/wp-includes/') !== false) {
            $scripts[] = $match[2];
        }
    }

    return array(
        'body_class' => isset($body_match[2]) ? $body_match[2] : '',
        'shell_start_html' => $parts[0],
        'shell_end_html' => $parts[1],
        'stylesheets' => array_values(array_unique(array_filter($stylesheets))),
        'inline_styles' => isset($style_matches[1]) ? array_values(array_filter($style_matches[1])) : array(),
        'scripts' => array_values(array_unique(array_filter($scripts))),
    );
}

function vx_site_build_shell_fragments_payload() {
    $bridge_page = vx_site_get_shell_bridge_page();
    if (!$bridge_page instanceof WP_Post) {
        return array();
    }

    $bridge_url = get_permalink($bridge_page);
    if (!$bridge_url) {
        return array();
    }

    $response = wp_remote_get($bridge_url, array('timeout' => 5));
    if (is_wp_error($response)) {
        return array();
    }

    return vx_site_extract_shell_fragments_from_html(wp_remote_retrieve_body($response));
}

function vx_site_register_rest_routes() {
    register_rest_route('vx-site/v1', '/shell', array(
        'methods' => 'GET',
        'callback' => function () {
            return rest_ensure_response(vx_site_build_shell_payload());
        },
        'permission_callback' => '__return_true',
    ));
}
add_action('rest_api_init', 'vx_site_register_rest_routes');

function vx_site_account_app_config() {
    $options = vx_site_get_options();
    $account_url = vx_site_build_shell_url((string) ($options['django_account_url'] ?: '/account/'));
    $account_path = rtrim((string) wp_parse_url($account_url, PHP_URL_PATH), '/') . '/';

    return array(
        'accountUrl' => esc_url_raw($account_url),
        'accountPath' => $account_path,
        'apiStateUrl' => esc_url_raw(home_url('/account-app/api/state/')),
        'apiLoginUrl' => esc_url_raw(home_url('/account-app/api/login/')),
        'apiSignupUrl' => esc_url_raw(home_url('/account-app/api/signup/')),
        'apiBuyUrl' => esc_url_raw(home_url('/account-app/api/buy/')),
        'apiRenewUrl' => esc_url_raw(home_url('/account-app/api/renew/')),
        'supportUrl' => esc_url_raw(home_url('/instructions/')),
    );
}

function vx_site_enqueue_account_app_assets() {
    wp_enqueue_style(
        'vx-site-account-app',
        VX_SITE_INTEGRATION_URL . 'assets/account-app.css',
        array('vx-site-integration'),
        VX_SITE_INTEGRATION_VERSION
    );
    wp_enqueue_script(
        'vx-site-account-app',
        VX_SITE_INTEGRATION_URL . 'assets/account-app.js',
        array(),
        VX_SITE_INTEGRATION_VERSION,
        true
    );
    wp_add_inline_script(
        'vx-site-account-app',
        'window.VXAccountAppConfig = ' . wp_json_encode(vx_site_account_app_config()) . ';',
        'before'
    );
}

function vx_site_account_app_shortcode() {
    vx_site_enqueue_account_app_assets();
    ob_start();
    ?>
    <div class="vx-native-account" data-vx-account-app>
        <div class="vx-native-account__skeleton" aria-hidden="true">
            <div class="vx-native-account__hero">
                <div class="vx-native-account__line vx-native-account__line-title"></div>
                <div class="vx-native-account__line vx-native-account__line-subtitle"></div>
                <div class="vx-native-account__chips">
                    <span class="vx-native-account__chip"></span>
                    <span class="vx-native-account__chip"></span>
                    <span class="vx-native-account__chip"></span>
                </div>
            </div>
            <div class="vx-native-account__grid">
                <div class="vx-native-account__card"></div>
                <div class="vx-native-account__card"></div>
                <div class="vx-native-account__card"></div>
                <div class="vx-native-account__card"></div>
            </div>
            <div class="vx-native-account__panel"></div>
        </div>
    </div>
    <?php
    return (string) ob_get_clean();
}
add_shortcode('vx_account_app', 'vx_site_account_app_shortcode');

function vx_site_register_page_meta() {
    $meta_config = array(
        'single' => true,
        'show_in_rest' => false,
        'auth_callback' => function () {
            return current_user_can('edit_pages');
        },
    );

    register_post_meta('page', 'vx_posts_enabled', $meta_config + array(
        'type' => 'boolean',
        'sanitize_callback' => 'rest_sanitize_boolean',
        'default' => false,
    ));
    register_post_meta('page', 'vx_posts_source', $meta_config + array(
        'type' => 'string',
        'sanitize_callback' => 'sanitize_text_field',
        'default' => 'all',
    ));
    register_post_meta('page', 'vx_posts_limit', $meta_config + array(
        'type' => 'integer',
        'sanitize_callback' => 'absint',
        'default' => 12,
    ));
    register_post_meta('page', 'vx_category_filters', $meta_config + array(
        'type' => 'array',
        'sanitize_callback' => 'vx_site_sanitize_int_array',
        'default' => array(),
    ));
    register_post_meta('page', 'vx_manual_post_ids', $meta_config + array(
        'type' => 'array',
        'sanitize_callback' => 'vx_site_sanitize_int_array',
        'default' => array(),
    ));
    register_post_meta('page', 'vx_page_path', $meta_config + array(
        'type' => 'string',
        'sanitize_callback' => 'vx_site_normalize_path',
        'default' => '/',
    ));
    register_post_meta('page', 'vx_feed_title', $meta_config + array(
        'type' => 'string',
        'sanitize_callback' => 'sanitize_text_field',
        'default' => '',
    ));
}
add_action('init', 'vx_site_register_page_meta');

function vx_site_sanitize_int_array($value) {
    if (!is_array($value)) {
        return array();
    }

    return array_values(array_filter(array_map('absint', $value)));
}

function vx_site_normalize_path($path) {
    $path = trim((string) $path);
    if ($path === '') {
        return '';
    }
    if ($path[0] !== '/') {
        $path = '/' . $path;
    }
    if ($path !== '/' && substr($path, -1) !== '/') {
        $path .= '/';
    }
    return $path;
}

function vx_site_add_settings_page() {
    add_options_page(
        'VX Site Settings',
        'VX Site',
        'manage_options',
        'vx-site-settings',
        'vx_site_render_settings_page'
    );
}
add_action('admin_menu', 'vx_site_add_settings_page');

function vx_site_add_import_page() {
    add_management_page(
        'Django Import',
        'Django Import',
        'manage_options',
        'vx-site-import',
        'vx_site_render_import_page'
    );
}
add_action('admin_menu', 'vx_site_add_import_page');

function vx_site_register_settings() {
    register_setting('vx_site_settings', 'vx_site_options', array(
        'type' => 'array',
        'sanitize_callback' => 'vx_site_sanitize_options',
        'default' => vx_site_default_options(),
    ));
}
add_action('admin_init', 'vx_site_register_settings');

function vx_site_sanitize_options($input) {
    $defaults = vx_site_default_options();
    return array(
        'cta_label' => sanitize_text_field($input['cta_label'] ?? $defaults['cta_label']),
        'price_label' => sanitize_text_field($input['price_label'] ?? $defaults['price_label']),
        'django_account_url' => esc_url_raw($input['django_account_url'] ?? $defaults['django_account_url']),
        'django_open_app_url' => esc_url_raw($input['django_open_app_url'] ?? $defaults['django_open_app_url']),
    );
}

function vx_site_render_settings_page() {
    $options = vx_site_get_options();
    ?>
    <div class="wrap">
        <h1>VX Site Settings</h1>
        <form method="post" action="options.php">
            <?php settings_fields('vx_site_settings'); ?>
            <table class="form-table" role="presentation">
                <tr>
                    <th scope="row"><label for="vx-site-cta-label">Primary CTA label</label></th>
                    <td><input id="vx-site-cta-label" name="vx_site_options[cta_label]" type="text" class="regular-text" value="<?php echo esc_attr($options['cta_label']); ?>"></td>
                </tr>
                <tr>
                    <th scope="row"><label for="vx-site-price-label">Price label</label></th>
                    <td><input id="vx-site-price-label" name="vx_site_options[price_label]" type="text" class="regular-text" value="<?php echo esc_attr($options['price_label']); ?>"></td>
                </tr>
                <tr>
                    <th scope="row"><label for="vx-site-django-account-url">Django account URL</label></th>
                    <td><input id="vx-site-django-account-url" name="vx_site_options[django_account_url]" type="url" class="regular-text" value="<?php echo esc_attr($options['django_account_url']); ?>"></td>
                </tr>
                <tr>
                    <th scope="row"><label for="vx-site-django-open-app-url">Django open-app URL</label></th>
                    <td><input id="vx-site-django-open-app-url" name="vx_site_options[django_open_app_url]" type="url" class="regular-text" value="<?php echo esc_attr($options['django_open_app_url']); ?>"></td>
                </tr>
            </table>
            <?php submit_button('Save settings'); ?>
        </form>
        <p>Use <code>[vx_primary_cta]</code> in Flatsome UX Builder HTML or text elements.</p>
    </div>
    <?php
}

function vx_site_render_import_page() {
    $default_path = ABSPATH . 'import-data/django-wordpress-export.json';
    $result = null;

    if (
        !empty($_POST['vx_site_import_submit'])
        && check_admin_referer('vx_site_import')
        && current_user_can('manage_options')
    ) {
        $path = sanitize_text_field(wp_unslash($_POST['vx_site_import_path'] ?? $default_path));
        $importer = new VX_Site_Importer();
        $result = $importer->import_from_file($path);
    }
    ?>
    <div class="wrap">
        <h1>Import Django Export</h1>
        <p>Run the Django exporter first, then import the generated JSON file from the shared <code>import-data</code> directory.</p>
        <?php if (is_array($result)) : ?>
            <div class="notice notice-success"><p><?php echo esc_html($result['message']); ?></p></div>
        <?php elseif (is_wp_error($result)) : ?>
            <div class="notice notice-error"><p><?php echo esc_html($result->get_error_message()); ?></p></div>
        <?php endif; ?>
        <form method="post">
            <?php wp_nonce_field('vx_site_import'); ?>
            <table class="form-table" role="presentation">
                <tr>
                    <th scope="row"><label for="vx-site-import-path">JSON path</label></th>
                    <td><input id="vx-site-import-path" name="vx_site_import_path" type="text" class="regular-text code" value="<?php echo esc_attr($default_path); ?>"></td>
                </tr>
            </table>
            <p class="submit">
                <button type="submit" class="button button-primary" name="vx_site_import_submit" value="1">Import content</button>
            </p>
        </form>
    </div>
    <?php
}

function vx_site_add_page_meta_box() {
    add_meta_box(
        'vx-site-page-feed',
        'VX Post Feed',
        'vx_site_render_page_meta_box',
        'page',
        'side',
        'default'
    );
}
add_action('add_meta_boxes', 'vx_site_add_page_meta_box');

function vx_site_default_page_path_for_post($post) {
    if (!$post instanceof WP_Post) {
        return '';
    }

    $front_page_id = (int) get_option('page_on_front');
    if ($front_page_id && (int) $post->ID === $front_page_id) {
        return '/';
    }

    if (!empty($post->post_name)) {
        return '/' . $post->post_name . '/';
    }

    return '';
}

function vx_site_render_page_meta_box($post) {
    wp_nonce_field('vx_site_page_meta', 'vx_site_page_meta_nonce');
    $enabled = (bool) get_post_meta($post->ID, 'vx_posts_enabled', true);
    $source = get_post_meta($post->ID, 'vx_posts_source', true) ?: 'all';
    $limit = absint(get_post_meta($post->ID, 'vx_posts_limit', true) ?: 12);
    $page_path = get_post_meta($post->ID, 'vx_page_path', true);
    if ($page_path === '') {
        $page_path = vx_site_default_page_path_for_post($post);
    }
    $feed_title = get_post_meta($post->ID, 'vx_feed_title', true) ?: '';
    $selected_categories = array_map('absint', (array) get_post_meta($post->ID, 'vx_category_filters', true));
    $selected_posts = array_map('absint', (array) get_post_meta($post->ID, 'vx_manual_post_ids', true));
    $categories = get_categories(array('hide_empty' => false));
    $posts = get_posts(array(
        'post_type' => 'post',
        'post_status' => array('publish', 'draft', 'future', 'pending', 'private'),
        'numberposts' => 200,
    ));
    ?>
    <p><label><input type="checkbox" name="vx_posts_enabled" value="1" <?php checked($enabled); ?>> Append post feed to this page</label></p>
    <p>
        <label for="vx-posts-source"><strong>Source</strong></label><br>
        <select id="vx-posts-source" name="vx_posts_source" class="widefat">
            <option value="all" <?php selected($source, 'all'); ?>>All posts</option>
            <option value="filtered" <?php selected($source, 'filtered'); ?>>Categories</option>
            <option value="manual" <?php selected($source, 'manual'); ?>>Manual selection</option>
        </select>
    </p>
    <p>
        <label for="vx-posts-limit"><strong>Limit</strong></label>
        <input id="vx-posts-limit" name="vx_posts_limit" type="number" min="1" max="100" class="small-text" value="<?php echo esc_attr($limit); ?>">
    </p>
    <p>
        <label for="vx-feed-title"><strong>Feed title</strong></label>
        <input id="vx-feed-title" name="vx_feed_title" type="text" class="widefat" value="<?php echo esc_attr($feed_title); ?>">
    </p>
    <p>
        <label for="vx-page-path"><strong>Public path</strong></label>
        <input id="vx-page-path" name="vx_page_path" type="text" class="widefat code" value="<?php echo esc_attr($page_path); ?>">
    </p>
    <p><strong>Categories</strong></p>
    <div style="max-height: 140px; overflow: auto; border: 1px solid #dcdcde; padding: 8px;">
        <?php foreach ($categories as $category) : ?>
            <label style="display:block; margin-bottom:4px;">
                <input type="checkbox" name="vx_category_filters[]" value="<?php echo esc_attr($category->term_id); ?>" <?php checked(in_array((int) $category->term_id, $selected_categories, true)); ?>>
                <?php echo esc_html($category->name); ?>
            </label>
        <?php endforeach; ?>
    </div>
    <p><strong>Manual posts</strong></p>
    <div style="max-height: 180px; overflow: auto; border: 1px solid #dcdcde; padding: 8px;">
        <?php foreach ($posts as $feed_post) : ?>
            <label style="display:block; margin-bottom:4px;">
                <input type="checkbox" name="vx_manual_post_ids[]" value="<?php echo esc_attr($feed_post->ID); ?>" <?php checked(in_array((int) $feed_post->ID, $selected_posts, true)); ?>>
                <?php echo esc_html($feed_post->post_title); ?>
            </label>
        <?php endforeach; ?>
    </div>
    <?php
}

function vx_site_save_page_meta($post_id) {
    if (!isset($_POST['vx_site_page_meta_nonce']) || !wp_verify_nonce(sanitize_text_field(wp_unslash($_POST['vx_site_page_meta_nonce'])), 'vx_site_page_meta')) {
        return;
    }
    if (defined('DOING_AUTOSAVE') && DOING_AUTOSAVE) {
        return;
    }
    if (!current_user_can('edit_page', $post_id)) {
        return;
    }

    update_post_meta($post_id, 'vx_posts_enabled', !empty($_POST['vx_posts_enabled']));
    update_post_meta($post_id, 'vx_posts_source', sanitize_text_field(wp_unslash($_POST['vx_posts_source'] ?? 'all')));
    update_post_meta($post_id, 'vx_posts_limit', absint($_POST['vx_posts_limit'] ?? 12));
    update_post_meta($post_id, 'vx_feed_title', sanitize_text_field(wp_unslash($_POST['vx_feed_title'] ?? '')));
    if (array_key_exists('vx_page_path', $_POST)) {
        $normalized_path = vx_site_normalize_path(wp_unslash($_POST['vx_page_path']));
        if ($normalized_path === '') {
            delete_post_meta($post_id, 'vx_page_path');
        } else {
            update_post_meta($post_id, 'vx_page_path', $normalized_path);
        }
    }
    update_post_meta($post_id, 'vx_category_filters', vx_site_sanitize_int_array($_POST['vx_category_filters'] ?? array()));
    update_post_meta($post_id, 'vx_manual_post_ids', vx_site_sanitize_int_array($_POST['vx_manual_post_ids'] ?? array()));
}
add_action('save_post_page', 'vx_site_save_page_meta');

function vx_site_filter_page_link($link, $post_id) {
    $path = get_post_meta($post_id, 'vx_page_path', true);
    if (!$path) {
        return $link;
    }

    $front_page_id = (int) get_option('page_on_front');
    if ($path === '/' && (int) $post_id !== $front_page_id) {
        return $link;
    }

    return home_url($path);
}
add_filter('page_link', 'vx_site_filter_page_link', 10, 2);

function vx_site_resolve_custom_page_path($wp) {
    if (is_admin() || empty($wp->request)) {
        return;
    }
    if (!empty($wp->query_vars['rest_route'])) {
        return;
    }
    if (
        strpos($wp->request, 'wp-admin') === 0
        || strpos($wp->request, 'wp-json') === 0
        || strpos($wp->request, 'wp-content') === 0
        || strpos($wp->request, 'wp-includes') === 0
        || strpos($wp->request, 'feed') === 0
    ) {
        return;
    }

    if ($wp->request === 'account' || strpos($wp->request, 'account/') === 0) {
        $account_page = vx_site_get_account_host_page();
        if ($account_page instanceof WP_Post) {
            $wp->query_vars = array('page_id' => (int) $account_page->ID);
            return;
        }
    }

    $path = vx_site_normalize_path($wp->request);
    $page_id = vx_site_find_page_by_path($path);
    if ($page_id) {
        $wp->query_vars = array('page_id' => $page_id);
    }
}
add_action('parse_request', 'vx_site_resolve_custom_page_path', 1);

function vx_site_disable_account_canonical_redirect($redirect_url, $requested_url) {
    $path = wp_parse_url((string) $requested_url, PHP_URL_PATH);
    $path = trim((string) $path, '/');
    if ($path === 'account' || strpos($path, 'account/') === 0) {
        return false;
    }
    return $redirect_url;
}
add_filter('redirect_canonical', 'vx_site_disable_account_canonical_redirect', 10, 2);

function vx_site_find_page_by_path($path) {
    global $wpdb;

    $post_id = $wpdb->get_var(
        $wpdb->prepare(
            "SELECT post_id FROM {$wpdb->postmeta} pm
             INNER JOIN {$wpdb->posts} p ON p.ID = pm.post_id
             WHERE pm.meta_key = 'vx_page_path'
               AND pm.meta_value = %s
               AND p.post_type = 'page'
               AND p.post_status IN ('publish', 'draft', 'private')
             LIMIT 1",
            $path
        )
    );

    return $post_id ? (int) $post_id : 0;
}

function vx_site_primary_cta_shortcode() {
    $options = vx_site_get_options();
    $label = trim($options['cta_label']);
    $price = trim($options['price_label']);
    $url = $options['django_account_url'] ?: '/account/';
    $content = esc_html($label);

    if ($price !== '') {
        $content .= ' <span class="vx-cta-price">' . esc_html($price) . '</span>';
    }

    return '<a class="button primary is-large vx-primary-cta" href="' . esc_url($url) . '">' . $content . '</a>';
}
add_shortcode('vx_primary_cta', 'vx_site_primary_cta_shortcode');

function vx_site_get_feed_posts($post_id) {
    $enabled = (bool) get_post_meta($post_id, 'vx_posts_enabled', true);
    if (!$enabled) {
        return array();
    }

    $source = get_post_meta($post_id, 'vx_posts_source', true) ?: 'all';
    $limit = max(1, absint(get_post_meta($post_id, 'vx_posts_limit', true) ?: 12));
    $query_args = array(
        'post_type' => 'post',
        'post_status' => 'publish',
        'posts_per_page' => $limit,
        'ignore_sticky_posts' => true,
    );

    if ($source === 'manual') {
        $ids = array_map('absint', (array) get_post_meta($post_id, 'vx_manual_post_ids', true));
        if (empty($ids)) {
            return array();
        }
        $query_args['post__in'] = $ids;
        $query_args['orderby'] = 'post__in';
    } elseif ($source === 'filtered') {
        $categories = array_map('absint', (array) get_post_meta($post_id, 'vx_category_filters', true));
        if (!empty($categories)) {
            $query_args['category__in'] = $categories;
        }
    }

    return get_posts($query_args);
}

function vx_site_render_feed_markup($post_id) {
    $posts = vx_site_get_feed_posts($post_id);
    if (empty($posts)) {
        return '';
    }

    $title = get_post_meta($post_id, 'vx_feed_title', true) ?: 'Latest guides';

    ob_start();
    ?>
    <section class="vx-post-feed">
        <div class="vx-post-feed__header">
            <h2><?php echo esc_html($title); ?></h2>
        </div>
        <div class="vx-post-feed__grid">
            <?php foreach ($posts as $feed_post) : ?>
                <article class="vx-post-feed__card">
                    <a class="vx-post-feed__link" href="<?php echo esc_url(get_permalink($feed_post)); ?>">
                        <h3><?php echo esc_html(get_the_title($feed_post)); ?></h3>
                        <p><?php echo esc_html(get_the_excerpt($feed_post)); ?></p>
                    </a>
                </article>
            <?php endforeach; ?>
        </div>
    </section>
    <?php
    return (string) ob_get_clean();
}

function vx_site_append_feed_to_content($content) {
    if (!is_singular('page') || !in_the_loop() || !is_main_query()) {
        return $content;
    }

    global $post;
    if (!$post instanceof WP_Post) {
        return $content;
    }

    return $content . vx_site_render_feed_markup($post->ID);
}
add_filter('the_content', 'vx_site_append_feed_to_content');

function vx_site_enqueue_assets() {
    wp_enqueue_style(
        'vx-site-integration',
        VX_SITE_INTEGRATION_URL . 'assets/site.css',
        array(),
        VX_SITE_INTEGRATION_VERSION
    );
}
add_action('wp_enqueue_scripts', 'vx_site_enqueue_assets');
