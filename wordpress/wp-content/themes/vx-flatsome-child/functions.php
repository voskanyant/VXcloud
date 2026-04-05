<?php

if (!defined('ABSPATH')) {
    exit;
}

function vx_flatsome_child_enqueue_styles()
{
    wp_enqueue_style('vx-flatsome-child', get_stylesheet_uri(), array(), '0.1.0');
    wp_enqueue_style(
        'vx-flatsome-child-site',
        get_stylesheet_directory_uri() . '/assets/css/site.css',
        array('vx-flatsome-child'),
        '0.1.0'
    );
}
add_action('wp_enqueue_scripts', 'vx_flatsome_child_enqueue_styles', 20);
