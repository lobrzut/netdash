# NetDash Roadmap

## Done (v1.3.26)

- [x] Add-service modal parity with edit (icon, category datalist, description, pin/login, Identyfikuj)

## Done (v1.3.25)

- [x] Uptime mini-indicator on service cards (online / offline / stale / unknown / error)
- [x] Homer-inspired card polish (category accent, hover lift, typography)
- [x] Empty states (pinned CTA, search no-results with clear button)
- [x] Settings About/appearance spacing cleanup
- [x] Search debounce + incremental pin toggle DOM patch
- [x] Homer YAML import (MVP: name, url, icon, category)

## Top gaps vs Homer / Dashy / Homepage

1. **YAML export + full Homer parity** — widgets, custom CSS from YAML, message banners, navbar links
2. **Docker / Proxmox / Kubernetes widgets** — container stats, VM status (Homepage/Dashy strength)
3. **Global search (⌘K)** — jump to any service/note/key across the dashboard
4. **Drag-and-drop layout** — reorder pins and categories without edit modal
5. **Multi-user / RBAC** — shared homelab with per-user pins and vault ACL

## Planned

- [ ] Homer YAML export
- [ ] Widget iframe / custom HTML blocks
- [ ] Service tags and multi-category filters
- [ ] Dark/light/auto schedule per theme
- [ ] PWA + optional public read-only mode
