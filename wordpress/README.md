# WordPress Public Site Scaffold

This directory contains the repo-managed parts of the WordPress migration:

- `wp-content/plugins/vx-site-integration`
  - registers the VX page-feed meta
  - imports the Django export bundle
  - appends post feeds to pages
  - preserves arbitrary public page paths
  - exposes simple CTA settings for Django-linked buttons
- `wp-content/themes/vx-flatsome-child`
  - child theme scaffold for the licensed Flatsome parent theme
- `import-data/`
  - shared drop zone for the Django export bundle

## Important

The actual Flatsome parent theme is proprietary and is not committed to this repository.
Install Flatsome through the normal WordPress admin workflow, then activate `VX Flatsome Child`.

## Migration Flow

1. Export Django content:

```bash
docker compose --env-file .env exec -T web python /app/web/manage.py export_wordpress_content
```

2. Open WordPress admin:

```text
/wp-admin/
```

3. Activate:

- `VX Site Integration`
- `VX Flatsome Child`

4. In WordPress:

- go to `Tools -> Django Import`
- import `/var/www/html/import-data/django-wordpress-export.json`

5. Install and activate the licensed Flatsome parent theme, then keep editing public pages in UX Builder.
