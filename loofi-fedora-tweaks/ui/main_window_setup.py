"""Reviewed apply coordination for saved Fedora setup configurations."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

SETUP_APPLICATION_REVIEW_BATCH_SIZE = 128


class MainWindowSetupMixin:
    """Coordinate existing app and settings reviews for a saved setup."""

    def _connect_setup_page(self, widget: Any) -> None:
        from ui.setup_configurations import SetupConfigurationsPage

        if not isinstance(widget, SetupConfigurationsPage):
            return
        widget.refreshRequested.connect(lambda owner=widget: self._start_setup_refresh(owner))
        widget.continueSetupRequested.connect(
            lambda setup_id, progress_id, owner=widget: self._continue_setup_after_batch(owner, setup_id, progress_id)
        )
        widget.compareRequested.connect(lambda setup_id, owner=widget: self._compare_setup(owner, setup_id))
        widget.applyRequested.connect(lambda setup_id, owner=widget: self._apply_setup(owner, setup_id))
        widget.importRequested.connect(lambda document, owner=widget: self._import_setup(owner, document))
        widget.profileReviewRequested.connect(
            lambda progress_id, profile, owner=widget: self._review_setup_profile(owner, progress_id, profile)
        )

    def _setup_idle(self: Any, page: Any) -> bool:
        if self._utility_operation_adapter is not None or getattr(self, "_application_review_state", None) is not None:
            page.set_status(self.tr("Another reviewed operation is in progress. Wait for it to finish."))
            return False
        return True

    def _start_setup_refresh(self: Any, page: Any) -> bool:
        """Read installed apps and supported user settings through the shared worker."""
        if not self._setup_idle(page):
            return False
        from core.tasks.tweaks import snapshot
        from services.software.installed_applications import InstalledApplicationService

        controller = self._profile_controller()
        platform_profile = self._platform_profile
        adapter = self._new_utility_operation_adapter(phase="inspection", operation_name=self.tr("Reading this computer"))
        adapter.finished.connect(lambda result: page.set_inventory(*result))
        adapter.failed.connect(page.set_status)
        adapter.cancelled.connect(lambda: page.set_status(self.tr("Computer reading was cancelled. No changes were made.")))
        page.set_status(self.tr("Reading installed desktop apps and supported user settings…"))

        def read() -> tuple[Any, tuple[Any, ...]]:
            inventory = InstalledApplicationService().snapshot(cancelled=lambda: adapter.cancel_requested)
            states = snapshot(platform_profile, controller.orchestrator.runtime,
                              is_cancelled=lambda: adapter.cancel_requested)
            return inventory, states

        return bool(adapter.start(read))

    def _import_setup(self: Any, page: Any, document: Any) -> bool:
        """Validate and atomically add an imported or newly assembled document."""
        if not self._setup_idle(page):
            return False
        from core.tasks.setup_configurations import SetupLibrary

        adapter = self._new_utility_operation_adapter(phase="inspection", operation_name=self.tr("Saving configuration"))
        adapter.finished.connect(lambda _identifier: page.set_status(self.tr("Configuration saved to the local library.")))
        adapter.failed.connect(page.set_status)
        adapter.cancelled.connect(lambda: page.set_status(self.tr("Saving configuration was cancelled.")))
        adapter.stopped.connect(page.reload_setup_library)
        page.set_status(self.tr("Saving configuration to the local library…"))
        return bool(adapter.start(lambda: SetupLibrary().add(document)))

    def _setup_scan(self: Any, document: Any, adapter: Any, controller: Any, *, discover_apps: bool) -> tuple[Any, ...]:
        from core.tasks.tweaks import _profile_desktop, snapshot, visible_tweaks
        from services.software.installed_applications import InstalledApplicationService

        inventory = InstalledApplicationService().snapshot(cancelled=lambda: adapter.cancel_requested)
        host_desktop = _profile_desktop(self._platform_profile)
        states: tuple[Any, ...] = ()
        if document.profile.settings and document.profile.desktop == host_desktop:
            allowed = {tweak.id for tweak in visible_tweaks(self._platform_profile)}
            requested = tuple(key for key, _value in document.profile.settings if key in allowed)
            states = snapshot(self._platform_profile, controller.orchestrator.runtime, tweak_ids=requested,
                              is_cancelled=lambda: adapter.cancel_requested)
        discovery = None
        installations: tuple[str, ...] = ()
        if discover_apps and document.applications:
            from services.software.application_discovery import ApplicationDiscoveryService

            discovery = ApplicationDiscoveryService().snapshot(cancelled=lambda: adapter.cancel_requested)
        if any(app.source == "flatpak" and app.installation not in {"user", "system"} for app in document.applications):
            from services.software.flatpak_maintenance import FlatpakMaintenanceService

            installations = FlatpakMaintenanceService().installations()
        return inventory, states, discovery, installations, host_desktop

    def _compare_setup(self: Any, page: Any, setup_id: str) -> bool:
        """Create a timestamped, read-only comparison from current host state."""
        if not self._setup_idle(page):
            return False
        from core.tasks.setup_configurations import SetupLibrary, available_flatpak_targets, compare_setup

        try:
            document = SetupLibrary().get(str(setup_id))
        except (OSError, ValueError) as exc:
            page.set_status(str(exc))
            return False
        adapter = self._new_utility_operation_adapter(phase="inspection", operation_name=self.tr("Comparing configuration"))
        controller = self._profile_controller()

        def show(result: tuple[Any, ...]) -> None:
            from PyQt6.QtWidgets import QInputDialog

            inventory, states, _discovery, installations, host_desktop = result
            page.set_inventory(inventory, states)
            targets: dict[str, str] = {}
            by_imported_scope: dict[str, str] = {}
            named_apps = [app for app in document.applications
                          if app.source == "flatpak" and app.installation not in {"user", "system"}]
            reserved_targets = {(app.ref, app.installation) for app in document.applications
                                if app.source == "flatpak" and app.installation in {"user", "system"}}
            for app in named_apps:
                if app.installation in by_imported_scope:
                    targets[app.identity] = by_imported_scope[app.installation]
                    continue
                choices = available_flatpak_targets(app.ref, installations, reserved_targets)
                if not choices:
                    continue
                choice, accepted = QInputDialog.getItem(
                    page, self.tr("Choose Flatpak installation"),
                    self.tr("Choose the local comparison target for %1. Imported name %2 is only a hint.")
                    .replace("%1", app.name or app.app_id).replace("%2", app.installation),
                    list(choices), 0, False,
                )
                if not accepted or choice not in choices:
                    page.set_status(self.tr("Flatpak target selection was cancelled. No changes were made."))
                    return
                targets[app.identity] = choice
                by_imported_scope[app.installation] = choice
                reserved_targets.add((app.ref, choice))
            if len(targets) < len(named_apps):
                page.set_status(self.tr("One or more imported Flatpak installations could not be mapped to a distinct local target. Those entries remain uncheckable."))
            page.show_comparison(compare_setup(document, setup_id, inventory, states,
                                               target_installations=targets, current_desktop=host_desktop))

        adapter.finished.connect(show)
        adapter.failed.connect(page.set_status)
        adapter.cancelled.connect(lambda: page.set_status(self.tr("Comparison was cancelled. No changes were made.")))
        page.set_status(self.tr("Checking current apps and settings…"))
        return bool(adapter.start(lambda: self._setup_scan(document, adapter, controller, discover_apps=False)))

    def _continue_setup_after_batch(self: Any, page: Any, setup_id: str, progress_id: str) -> bool:
        """Recheck the next app batch while keeping one in-session progress record."""
        if (getattr(page, "_active_progress_id", "") != progress_id
                or getattr(page, "_active_document_id", "") != setup_id):
            page.set_status(self.tr("The previous app review is no longer active. Compare and start a fresh review."))
            return False
        return bool(self._apply_setup(page, setup_id, continuation_progress_id=progress_id))

    def _apply_setup(self: Any, page: Any, setup_id: str, *, continuation_progress_id: str = "") -> bool:
        """Recheck current state, then sequence fresh app and profile reviews."""
        if not self._setup_idle(page):
            return False
        from core.tasks.setup_configurations import SetupLibrary

        try:
            document = SetupLibrary().get(str(setup_id))
        except (OSError, ValueError) as exc:
            page.set_status(str(exc))
            return False
        adapter = self._new_utility_operation_adapter(phase="inspection", operation_name=self.tr("Preparing setup review"))
        controller = self._profile_controller()
        scan_results: list[Any] = []
        adapter.finished.connect(scan_results.append)
        adapter.stopped.connect(lambda: self._prepare_setup_reviews(
            page, setup_id, document, scan_results[0], continuation_progress_id=continuation_progress_id
        ) if scan_results else None)
        adapter.failed.connect(page.set_status)
        adapter.cancelled.connect(lambda: page.set_status(self.tr("Setup preparation was cancelled. No changes were made.")))
        page.set_status(self.tr("Rechecking this computer and local app sources…"))
        return bool(adapter.start(lambda: self._setup_scan(document, adapter, controller, discover_apps=True)))

    def _prepare_setup_reviews(self: Any, page: Any, setup_id: str, document: Any, scan: tuple[Any, ...],
                               *, continuation_progress_id: str = "") -> None:
        from PyQt6.QtWidgets import QMessageBox, QInputDialog
        from core.tasks.setup_configurations import SetupProgressStore, available_flatpak_targets, compare_setup

        inventory, states, discovery, installations, host_desktop = scan
        previous_run = None
        if continuation_progress_id:
            try:
                previous_run = next((record for record in SetupProgressStore().list()
                                     if record.get("id") == continuation_progress_id), None)
            except (OSError, ValueError) as exc:
                page.set_status(self.tr("Active setup progress could not be read; no additional changes were started. %1")
                                .replace("%1", str(exc)))
                return
            if (previous_run is None or previous_run.get("setup_id") != setup_id
                    or previous_run.get("setup_digest") != document.digest):
                page.set_status(self.tr("The active setup no longer matches this configuration. Compare and start a fresh review."))
                return
        previous_steps = previous_run.get("steps", {}) if previous_run is not None else {}
        previous_targets = previous_run.get("target_installations", {}) if previous_run is not None else {}
        previously_skipped_apps = {key.partition(":")[2] for key, state in previous_steps.items()
                                   if key.startswith("app:") and state.get("status") == "skipped"}
        previously_skipped_settings = {key.partition(":")[2] for key, state in previous_steps.items()
                                       if key.startswith("setting:") and state.get("status") == "skipped"}
        targets: dict[str, str] = {}
        skipped_steps: list[str] = []
        named_target_cache: dict[str, str] = {}
        unconfirmed_named_targets: list[Any] = []
        reserved_targets = {(app.ref, app.installation) for app in document.applications
                            if app.source == "flatpak" and app.installation in {"user", "system"}}
        for app in document.applications:
            if app.source != "flatpak" or app.installation in {"user", "system"}:
                continue
            if continuation_progress_id and app.identity in previous_targets:
                previous_target = previous_targets[app.identity]
                if previous_target not in installations:
                    page.set_status(self.tr("A confirmed Flatpak target is no longer available. Start a fresh setup review before continuing."))
                    return
                targets[app.identity] = previous_target
                named_target_cache[app.installation] = previous_target
                reserved_targets.add((app.ref, previous_target))
                continue
            if app.identity in previously_skipped_apps:
                continue
            if app.installation in named_target_cache:
                targets[app.identity] = named_target_cache[app.installation]
                reserved_targets.add((app.ref, named_target_cache[app.installation]))
                continue
            choices = available_flatpak_targets(app.ref, installations, reserved_targets)
            if not choices:
                unconfirmed_named_targets.append(app)
                continue
            choice, accepted = QInputDialog.getItem(
                page, self.tr("Choose Flatpak installation"),
                self.tr("Choose the local target for %1. Imported name %2 is only a hint.")
                .replace("%1", app.name or app.app_id).replace("%2", app.installation),
                list(choices), 0, False,
            )
            if not accepted or choice not in choices:
                page.set_status(self.tr("Flatpak target selection was cancelled. No changes were made."))
                return
            targets[app.identity] = choice
            named_target_cache[app.installation] = choice
            reserved_targets.add((app.ref, choice))

        if continuation_progress_id and targets != previous_targets:
            page.set_status(self.tr("Confirmed Flatpak targets changed during the active review. Compare and start a fresh review."))
            return

        comparison = compare_setup(
            document, setup_id, inventory, states,
            target_installations=targets, current_desktop=host_desktop,
        )
        page.set_inventory(inventory, states)
        page.show_comparison(comparison)
        app_entries = {entry.identity: entry for entry in comparison.entries if entry.kind == "application"}
        setting_entries = {entry.identity: entry for entry in comparison.entries if entry.kind == "setting"}
        uncheckable_apps = [app for app in document.applications
                            if app.identity not in previously_skipped_apps
                            and app_entries.get(app.identity) is not None
                            and app_entries[app.identity].status in {"unavailable", "needs_target"}]
        blocked_settings = [entry for entry in setting_entries.values()
                            if entry.identity not in previously_skipped_settings
                            and entry.status in {"unavailable", "wrong_desktop"}]
        if unconfirmed_named_targets:
            uncheckable_apps.extend(app for app in unconfirmed_named_targets if app not in uncheckable_apps)
        if uncheckable_apps:
            names = ", ".join(app.name or app.app_id for app in uncheckable_apps[:8])
            if len(uncheckable_apps) > 8:
                names += self.tr(" and %1 more").replace("%1", str(len(uncheckable_apps) - 8))
            answer = QMessageBox.question(
                page, self.tr("Skip applications that could not be checked?"),
                self.tr("These applications could not be checked in the selected local installation: %1. Skip their steps for this review? You can review local app sources and compare again later.")
                .replace("%1", names),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                page.set_status(self.tr("Review stopped because some applications could not be checked. No changes were made; review local sources and compare again."))
                page.routeRequested.emit("software:repos", {})
                return
            skipped_steps.extend(f"app:{app.identity}" for app in uncheckable_apps)

        if blocked_settings:
            names = ", ".join(entry.title for entry in blocked_settings[:8])
            if len(blocked_settings) > 8:
                names += self.tr(" and %1 more").replace("%1", str(len(blocked_settings) - 8))
            answer = QMessageBox.question(
                page, self.tr("Skip settings that could not be checked?"),
                self.tr("These settings are unavailable or target another desktop: %1. Skip them for this review? They will remain unverified.")
                .replace("%1", names),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                page.set_status(self.tr("Review stopped because some settings could not be checked. No changes were made."))
                return
            skipped_steps.extend(f"setting:{entry.identity}" for entry in blocked_settings)

        skipped_app_ids = {step.partition(":")[2] for step in skipped_steps if step.startswith("app:")}
        missing = [app for app in document.applications
                   if app.identity not in skipped_app_ids
                   and app.identity not in previously_skipped_apps
                   and app_entries.get(app.identity) is not None
                   and app_entries[app.identity].status in {"missing", "other_installation"}]
        changed_settings = tuple((key, value) for key, value in document.profile.settings
                                 if key not in previously_skipped_settings
                                 and setting_entries.get(key) is not None and setting_entries[key].status == "differs")
        profile = replace(document.profile, settings=changed_settings)
        application_batch = missing[:SETUP_APPLICATION_REVIEW_BATCH_SIZE]
        deferred_apps = missing[SETUP_APPLICATION_REVIEW_BATCH_SIZE:]
        selected_records: list[Any] = []
        installable_apps: list[Any] = []
        unmatched_apps: list[Any] = []
        selection = None
        if missing:
            from core.tasks import ApplicationCatalog, ApplicationContext, TaskContext
            from services.software.application_discovery import ApplicationDiscoveryCatalog

            context = ApplicationContext.from_task_context(TaskContext.from_platform_profile(self._platform_profile))
            catalog = ApplicationDiscoveryCatalog(
                ApplicationCatalog(), discovery.records if discovery is not None else (),
                installed_identities=frozenset((item.installation, item.ref) for item in inventory.applications if item.source == "flatpak"),
            )
            discovery_records = discovery.records if discovery is not None else ()
            for app in application_batch:
                target = targets.get(app.identity, app.installation)
                candidates = [
                    record for record in discovery_records
                    if record.source == app.source and (
                        (app.source == "fedora" and record.package_id == app.app_id)
                        or (app.source == "flatpak" and record.metadata.get("ref") == app.ref
                            and record.metadata.get("installation") == target)
                    )
                ]
                candidates = sorted({record.id: record for record in candidates}.values(), key=lambda record: record.id)
                if not candidates:
                    unmatched_apps.append(app)
                    continue
                labels = []
                for record in candidates:
                    if record.source == "fedora":
                        label = f"RPM · {record.metadata.get('repo_id', 'local repo')} · {record.metadata.get('version', '')}.{record.metadata.get('arch', '')}"
                    else:
                        label = f"Flatpak · {record.metadata.get('remote', 'local remote')} · {record.metadata.get('installation', '')}"
                    labels.append(f"{label} · {record.id}")
                hint = f" Imported source hint: {app.source_hint}." if app.source_hint else ""
                label, accepted = QInputDialog.getItem(
                    page, self.tr("Choose a local application source"),
                    self.tr("Choose the current local source for %1.%2")
                    .replace("%1", app.name or app.app_id).replace("%2", hint),
                    labels, 0, False,
                )
                if not accepted or label not in labels:
                    page.set_status(self.tr("Local application source selection was cancelled. No changes were made."))
                    return
                selected_records.append(candidates[labels.index(label)])
                installable_apps.append(app)

        if unmatched_apps:
            names = ", ".join(app.name or app.app_id for app in unmatched_apps[:8])
            if len(unmatched_apps) > 8:
                names += self.tr(" and %1 more").replace("%1", str(len(unmatched_apps) - 8))
            answer = QMessageBox.question(
                page, self.tr("Skip applications missing from local sources?"),
                self.tr("No current local source was found for: %1. Review app sources separately, or explicitly skip these steps for this review?")
                .replace("%1", names),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                page.set_status(self.tr("Review stopped because some requested apps are not available from a local source. Review app sources, then compare again."))
                page.routeRequested.emit("software:repos", {})
                return
            skipped_steps.extend(f"app:{app.identity}" for app in unmatched_apps)

        if selected_records:
            try:
                selection = catalog.build_selection(tuple(record.id for record in selected_records), context=context,
                                                    title=self.tr("Install apps for %1").replace("%1", document.name))
            except (RuntimeError, ValueError) as exc:
                page.set_status(self.tr("The selected local app sources could not be reviewed. No setup changes were started. %1")
                                .replace("%1", str(exc)))
                return
            from core.actions.bundles import ActionBundle
            if len(selection.bundle.items) != len(installable_apps):
                page.set_status(self.tr("The local app selection could not be mapped exactly. No setup changes were started."))
                return
            from core.actions.bundles import ActionBundleItem
            items = tuple(replace(cast(ActionBundleItem, item), item_id=app.identity, position=index)
                          for index, (item, app) in enumerate(zip(selection.bundle.items, installable_apps)))
            bundle = ActionBundle.applications(
                items, title=self.tr("Install apps for %1").replace("%1", document.name),
                description=self.tr("Review each exact local app source, install scope, and verified result."),
                metadata={**dict(selection.bundle.metadata), "catalog": "loofi.setup/v1", "setup_id": setup_id,
                          "variant": context.variant.value},
            )
            selection = replace(selection, bundle=bundle)

        try:
            progress_store = SetupProgressStore()
            progress_store.reconcile(setup_id, document.digest, comparison, active_run_id=continuation_progress_id,
                                     target_installations=targets)
        except (OSError, ValueError) as exc:
            page.set_status(self.tr("Previous setup progress could not be reconciled; no change was started. %1").replace("%1", str(exc)))
            return

        if not missing and not changed_settings and not skipped_steps:
            page.set_status(self.tr("This configuration already matches the latest computer reading."))
            return
        steps = [f"app:{app.identity}" for app in missing]
        steps.extend(step for step in skipped_steps if step not in steps)
        steps.extend(f"setting:{key}" for key, _value in changed_settings)
        if continuation_progress_id:
            try:
                current = next((record for record in progress_store.list()
                                if record.get("id") == continuation_progress_id), None)
            except (OSError, ValueError) as exc:
                page.set_status(self.tr("Active setup progress could not be read; no change was started. %1").replace("%1", str(exc)))
                return
            if current is None or any(step not in current.get("steps", {}) for step in steps):
                page.set_status(self.tr("Newly changed items need a separate fresh setup review. No additional change was started."))
                return
            if any(current["steps"].get(step, {}).get("status") in {"succeeded", "interrupted", "failed", "unavailable"}
                   for step in steps):
                page.set_status(self.tr("A previously reviewed item changed again. Start a fresh setup review before continuing."))
                return
            progress_id = continuation_progress_id
        else:
            try:
                progress_id = progress_store.start(setup_id, document.digest, steps, target_installations=targets)
            except (OSError, ValueError) as exc:
                page.set_status(self.tr("Setup progress could not be saved; no change was started. %1").replace("%1", str(exc)))
                return
        page.begin_progress(progress_id, setup_id, profile)
        if skipped_steps and not page.record_skipped_steps(
                progress_id, tuple(skipped_steps),
                self.tr("Selected unavailable steps were explicitly skipped and saved. They are not marked successful.")):
            return
        if selection is not None:
            self._review_utility_bundle(page, selection)
        elif deferred_apps:
            page.set_status(self.tr("The first app group is done for this review. Rechecking the remaining apps."))
            page.continueSetupRequested.emit(setup_id, progress_id)
        elif changed_settings:
            page.finish_setup_without_apps()
        elif skipped_steps:
            page.set_status(self.tr("Requested unavailable steps were explicitly skipped. Compare again to verify the computer."))

    def _review_setup_profile(self: Any, page: Any, progress_id: str, profile: Any) -> bool:
        """Freshly review profile values after every requested app is verified."""
        if not self._setup_idle(page):
            return False
        from core.tasks.setup_configurations import SetupProgressStore
        try:
            for identifier, _value in profile.settings:
                SetupProgressStore().update(progress_id, f"setting:{identifier}", "running")
        except (OSError, ValueError) as exc:
            page.set_status(self.tr("Settings review progress could not be saved; no setting was changed. %1").replace("%1", str(exc)))
            return False
        controller = self._profile_controller()
        adapter = self._new_utility_operation_adapter(phase="review", operation_name=self.tr("Reviewing desktop settings"))
        reviews: list[Any] = []
        adapter.finished.connect(reviews.append)
        adapter.failed.connect(lambda message: page.record_profile_review_stopped(
            progress_id, profile, "failed", self.tr("Desktop settings review failed. No changes were made. %1").replace("%1", str(message))))
        adapter.cancelled.connect(lambda: page.record_profile_review_stopped(
            progress_id, profile, "interrupted", self.tr("Desktop settings review was cancelled. No changes were made.")))
        adapter.stopped.connect(lambda: self._show_setup_profile_review(page, progress_id, profile, reviews[0]) if reviews else None)
        page.set_status(self.tr("Checking the current values and supported targets…"))
        from core.tasks.tweak_profiles import review_profile
        started = bool(adapter.start(lambda: review_profile(profile, controller, is_cancelled=lambda: adapter.cancel_requested)))
        if not started:
            page.record_profile_review_stopped(progress_id, profile, "interrupted",
                                               self.tr("Desktop settings review could not be started. No changes were made."))
        return started

    def _show_setup_profile_review(self: Any, page: Any, progress_id: str, profile: Any, review: Any) -> None:
        from PyQt6.QtWidgets import QDialog
        from core.tasks.tweak_profiles import ProfileEntryResult, ProfileResult, apply_profile
        from ui.tweak_profiles import ProfileSelectionDialog

        page.set_status(self.tr("Review each setting. Selected changes are checked again before they are applied."))
        rows = [(entry.id, f"{entry.title}: {entry.before or '?'} → {entry.value} [{entry.status}] {entry.message}", entry.status == "ready")
                for entry in review.entries]
        dialog = ProfileSelectionDialog(
            self.tr("Review settings: %1").replace("%1", profile.name),
            self.tr("Apply only the checked settings. Each setting uses the existing fresh review and independent verification."),
            rows, page, accept_label=self.tr("Apply selected settings"),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            page.record_profile_review_stopped(progress_id, profile, "interrupted",
                                               self.tr("Desktop settings review was cancelled. No changes were made."))
            return
        selected = dialog.selected_ids()
        if not selected:
            page.skip_profile_step(progress_id, profile)
            return
        if not self._setup_idle(page):
            return
        from core.tasks.setup_configurations import SetupProgressStore
        try:
            for identifier in selected:
                SetupProgressStore().update(progress_id, f"setting:{identifier}", "running")
        except (OSError, ValueError) as exc:
            page.set_status(self.tr("Settings progress could not be saved, so no setting was changed. %1").replace("%1", str(exc)))
            return
        controller = self._profile_controller()
        adapter = self._new_utility_operation_adapter(phase="change", operation_name=self.tr("Applying reviewed desktop settings"))
        results: list[Any] = []
        adapter.finished.connect(results.append)
        adapter.failed.connect(lambda message: page.finish_profile(ProfileResult(
            "failed", tuple(ProfileEntryResult(identifier, "failed", str(message)) for identifier in selected), str(message)
        )))
        adapter.cancelled.connect(lambda: page.finish_profile(ProfileResult(
            "interrupted", tuple(ProfileEntryResult(identifier, "interrupted", "Application was cancelled.") for identifier in selected),
            self.tr("Applying desktop settings was cancelled; compare again before another review."),
        )))
        adapter.stopped.connect(lambda: page.finish_profile(results[0]) if results else None)
        page.set_status(self.tr("Applying selected settings one at a time…"))
        if not adapter.start(lambda: apply_profile(review, controller, confirmed=True, selected_ids=selected,
                                                   is_cancelled=lambda: adapter.cancel_requested)):
            page.set_status(self.tr("Desktop settings could not be started. Compare again before continuing."))
