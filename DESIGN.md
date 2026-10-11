# Loofi Fedora Tweaks Design

The maintained GUI is a native PyQt6 control center. Overview is the default
start page; desktop settings, software, maintenance, and Activity use one
consistent presentation system. KDE is the first platform targeted by
automated qualification. GNOME shares the same system and capability-aware
behavior.

## Identity and themes

Use the existing Loofi logo and its blue-violet identity. Preserve native
window chrome and the desktop font. System mode selects Loofi light or dark
from the desktop's color scheme; saved explicit selections take precedence.
High contrast preserves its dedicated accessible palette. Theme changes must
not change geometry, navigation, selection, or pending operations.

| Semantic role | Light | Dark |
| --- | --- | --- |
| Window | #F4F6FB | #141823 |
| Surface | #FFFFFF | #1D2331 |
| Raised surface | #E9EDF7 | #283145 |
| Text | #182034 | #F2F5FC |
| Supporting text | #556178 | #B0BDD2 |
| Accent | #5B4FD6 | #A59AFF |
| Control border | #7B89A0 | #62728D |
| Focus | #3F6AE0 | #83B9FF |

Runtime colors are resolved exclusively through SemanticPalette in
`ui.design`. Extend existing semantic roles rather than adding page-local
colors. Text contrast is at least 4.5:1; meaningful control boundaries and
focus indicators are at least 3:1. Status always includes text.
Ordinary table text follows the active Qt palette. Rows with semantic status
colors retain a status role and are recolored after theme changes without
rebuilding the table or losing selection.

## Typography and geometry

Use the system font with page headings at 1.6 times the body size, section
headings at 1.15, and supporting text at 0.95. Headings are upright. The named
spacing scale is 4, 8, 12, 16, 24, 32 logical pixels. Minimum control height is
36; navigation rows are at least 44. Content remains bounded to 1120 pixels.
Reading text wraps; numerical values retain explicit units and provenance.

The sidebar contains Overview, Tweaks, Apps, Updates, Health, Activity, and an
explicit Tools disclosure. Tools contains System, Storage, Network, Security,
and Logs. Settings stays at the bottom. Search belongs to the page header and
Ctrl+K. Narrow windows use icon navigation with accessible names and tooltips.
Tools sub-navigation projects existing catalog sections; it must never add a
second registry or expose retired product surfaces.

## Page families

- Overview: CPU, RAM, GPU, and storage are the first four panels, followed by
  network, disk activity, temperatures, and battery. A compact maintenance
  section has up to three relevant next steps; introduction and guides follow
  the system overview. Use four, two, or one columns according to available
  width and font size. At 1280x800 with standard text, the four primary
  resource panels are visible without scrolling.
- Tweaks: Settings and Profiles subviews within one route. Settings use compact
  grouped rows with an upfront user/computer scope label, requested value,
  verified readback, and any separate session-activation result. Profiles hold
  the library and copy editor; compare and final review remain dialogs.
- Apps: Catalog, Installed, and Sources tabs. Catalog has source summaries and
  a fixed selection/review area with Show selected, individual deselection,
  and Clear selection. The shared review dialog shows exact source, package
  identifier, and installation scope without requiring expansion.
- Updates: independent System, Flatpak, and Firmware source sections.
- Health: symptom, inspection, evidence, reviewed fix, verified result.
- Activity: filterable saved results, before/after facts, and recovery details.
- Tools: shared scaffolding, readable tables, and explicit details.

Use panels for related information and divided rows for individual settings.
Avoid decorative gradients, unnecessary nested cards, duplicated page titles,
and nested vertical scrolling. Every page has one main scroll owner.
Scrollable cards and content columns may shrink to their wrapped-text height
at the available width. Hidden Health views must not reserve vertical space
in the active workflow or push maintenance below an empty scroll region.

## Interaction and truth

Shared controls cover normal, hover, focus, pressed, disabled, loading, error,
and success. Only short user-triggered transitions are appropriate. Search
opens and focuses the matching page/control; it never executes a change.

Persistent host changes remain exclusively owned by OperationController and
Action Center. Pending requests and independently verified values are distinct.
Restore previous value and Use Loofi standard value are distinct actions.
Review dialogs default to cancellation. A global status surface survives
navigation, including operation name, origin page, return action, failure, and
pending verification. Ordinary successful inspections report on their owning
page. Activity links resolve only actual run IDs; no historical identity is
synthesized for an operation that has none.

Profile drafts persist while switching Tweaks subviews. Leaving the editor for
another profile offers Save, Discard, or Cancel. Save and review chains from
the worker's captured successful terminal result; save failure, cancellation,
or late completion after shutdown cannot authorize a review or application.

Global search projects only settings supported by the current desktop from the
canonical catalog. Activating a setting clears view filters, scrolls to the
row, and focuses its control or availability explanation; it never selects a
new value. Installed search filters the captured inventory without refreshing
or merging duplicate app names across installation scopes.

Review dialogs begin with Cancel as the default and Escape action. Return from
search results, lists, or other review content must not apply a change; Return
on a deliberately focused, clearly named apply button remains available. The
responsive Tweaks toolbar keeps search, refresh, and cancel visible and wraps
them according to available width and font metrics. Profile import, export,
and preset actions live in the keyboard-accessible library view.

All Apps tabs and Tweaks subviews expose meaningful accessible names, keyboard
navigation, and focus return. Text remains usable at 100–200% scaling and with
larger system fonts.

Activity uses that label consistently in headings, tooltips, and accessible
names. First visit loads the 25 latest local Loofi runs asynchronously; external
sources remain explicitly refreshed. Exact run links resolve the requested
identity directly and report missing history without substituting another run.

Metrics distinguish ready, sampling, unavailable, error, and stale. Missing or
failed readings are never numeric zero. Graph history is memory-only and
bounded to 60 points. Overview and Monitor share a visibility-aware worker;
collection stops while hidden/minimized. Sleeping GPUs are not polled. Saved
maintenance timestamps describe actual observations, never a new check.

## Qualification

Automated rendering and interaction checks should cover reachable main and
tool views at 900x650, 1280x800, and 1600x900, with 100%, 150%, and 200% Qt
scaling, in light, dark, and high contrast. Include keyboard focus, larger text,
long translations, unavailable data, and workers finishing during
navigation/shutdown. Report the boundary of offscreen or VM evidence clearly;
physical KDE, GNOME, assistive technology, and GPU behavior are not manual
acceptance requirements.
