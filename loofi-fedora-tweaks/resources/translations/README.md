# English source strings

Loofi Fedora Tweaks ships an English-only interface. This directory retains
the Qt Linguist source catalog as a partial record of English UI strings; it
is not a complete extraction of the current interface, an accessibility check,
or evidence that the product is ready for translation.

## Files

- `en.ts` - partial English source-string inventory

The application does not load system-locale translations and does not package
non-English catalogs. `python3 scripts/check_translation_inventory.py --check`
keeps remaining source locators valid; a future localization effort still needs
to extract current `self.tr()` strings, preserve placeholders and plurals, add
translator loading and packaging, and validate translations with reviewers.
Long-text UI validation uses English stress strings.

Do not add or compile another locale without an explicit product-scope change.
