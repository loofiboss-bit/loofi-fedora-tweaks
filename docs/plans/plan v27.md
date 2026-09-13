# Plan för v27.0.0 — Fedora Maintenance Core

## V27.0.1 release decision

The reviewed Core implementation is released as v27.0.1 because the historical
v27.0.0 Marketplace Enhancement tag must remain unchanged. Automated
qualification is the blocking release gate for this version: the maintained
surface measures 86.95% coverage against an 85% threshold. The repository-wide
90% goal and physical/manual Fedora qualification are explicitly deferred to a
follow-up release under the user's release decision; no manual result is
inferred from rootless or offscreen evidence.

## Bedömning

- **Teknisk grund: stark.** Full verifiering passerar: 7 151 tester, 61 hoppade, 86,40 % täckning, rena lint/type/arkitekturkontroller, byggbara RPM-paket och inga identifierade medium/höga Bandit-fynd.
- **Produktomfång: ohållbart.** 29 plugins, 81 rutter, 74 systemåtgärder och cirka 100 000 produktkodrader gör appen svår att förstå och underhålla.
- **Användarresa:** Home är delvis motsägelsefullt före första kontrollen; Updates är funktionellt men splittrat; Troubleshooting är sunt och tydligt; Action Center är säkert men överlastat; Applications duplicerar systemets programbutik och är Plasma-specifikt.
- **Plattformsstöd:** produkten är egentligen Fedora KDE 44-fokuserad. Desktopdetektering styr nästan inga funktioner, Atomic-stödet är ofullständigt kvalificerat och flera hårdvaruverktyg gör snäva antaganden.
- **Tillgänglighet:** grundkomponenterna har bra namn och disclosures, men 200 % text skär av navigation och den nuvarande rapporten påstår fokusbevis trots att manifestet inte observerade tangentbordsfokus.
- **Publicering:** v26.0.3 publicerades den 13 september 2026 med grön CI och lyckad COPR-build 10981363, men `master`-README och flera versionsdokument säger fortfarande “local candidate”. Detta måste rättas omedelbart. [GitHub-release](https://github.com/loofiboss-bit/loofi-fedora-tweaks/releases/tag/v26.0.3)

## Produkt- och implementationsändringar

1. **Stäng v26 korrekt**
   - Synka README, roadmap, arkitektur, release notes, race lock och publik evidens till den verkliga v26.0.3-statusen.
   - Validera tagg, GitHub-artifakter, checksummor, CI, COPR-repository och installerbart RPM från publik källa.

2. **Kapa till fem destinationer**
   - **Home:** systemstatus, en rekommenderad nästa åtgärd och högst fem vanliga uppgifter.
   - **Updates & Apps:** System, Flatpak och firmware; programinstallation lämnas över neutralt till installerad programbutik via AppStream/XDG.
   - **System Health:** System Check, symptomstyrd felsökning, lagring, hårdvarustatus och support bundle.
   - **Protection & Recovery:** brandvägg/exponering, backup, exakta DNF/rpm-ostree-återställningar och aktivitetshistorik.
   - **Changes:** nuvarande Action Center, omgjort till en linjär gransknings- och verifieringsresa. Appinställningar nås via ett separat kugghjul, inte en sjätte destination.
   - Ta bort Desktop som produktområde; erbjud endast capability-detekterade länkar till skrivbordsmiljöns egna inställningar.

3. **Ta bort specialistprodukten helt**
   - Radera AI Lab, Agents, Automation, Loofi Link, State Teleport, Gaming, Development, generell virtualisering/GPU passthrough, Community/Marketplace, extensions, profiler och tillhörande legacy-rutter.
   - Behåll loggar endast som diagnostiskt underlag och supportexport.
   - Ta bort egna theme/dotfile/window-, fan-, GPU-switch-, generisk batteri- och GRUB-mutationer.
   - Ta bort dead-end-kontroller som “Schedule Update” och generell “Rollback Last Update”.
   - Ta bort Flatpak-distributionen; den nuvarande omfattande host-access-sandboxen passar inte en privilegierad systemapp. Behåll COPR-RPM och förbered officiell Fedora package review.

4. **Gör kärnan verkligt Fedora-neutral**
   - Inför en immutable `PlatformProfile` med Fedora-version, arkitektur, desktop, session och deployment-backend: `dnf5`, `rpm_ostree`, `bootc` eller `unknown`.
   - Låt samma profil styra navigation, readiness, Action Center, native handoffs och support bundle.
   - Okänd detektion får aldrig falla tillbaka till Workstation, Traditional eller “ingen omstart behövs”.
   - Ersätt KDE44 Readiness med desktopneutral Fedora Readiness; desktopkontroller laddas endast när rätt miljö faktiskt identifierats.
   - Visa endast åtgärder där capability, risk, autentisering, verifiering och återställningsmöjlighet är kända.

5. **Förenkla huvudresorna**
   - Home visar “No system check has been run yet” utan falsk varning och erbjuder en enda `Run system check`.
   - Updates följer strikt `Check → Select source → Review changes → Run → Verify`, med delprogress, avbrytning och källspecifika fel.
   - Changes visar `Needs attention` och `Recent`, en state-driven primärknapp och fem begripliga delar: ändring, risk, autentisering, verifiering och återställning.
   - Guided/review-first blir standard. Direktkörning tillåts bara för verifierbara låg-riskåtgärder.
   - Global sökning visar sidor först; systemåtgärder får ett separat läge och aktiveras inte med enkelklick.
   - Navigationen växlar till en kompakt väljare när fönsterbredd, DPI eller textskala gör två kolumner olämpliga.

## Publika gränssnitt och säkerhetsgränser

- Behåll GUI och en reducerad CLI: `info`, `check`, `updates`, `troubleshoot`, `changes list/show/apply/verify`, `activity`, `doctor` och `support-bundle`.
- Ta bort lokal Web API, D-Bus-daemon, deras systemd-enheter, RPM-subpaket, beroenden och dokumentation.
- Detta är en avsiktligt brytande majorversion; borttagna CLI-kommandon och legacy-rutter bevaras inte.
- Bevara endast säkerhets- och historikrelevant v26-data: systemkontroller, update snapshots, planer, runs, aktivitet och backupmetadata. Specialistdata lämnas orörd på disk men läses eller migreras inte.
- Alla beständiga systemändringar går genom Action Center. UI får inte importera muterande utilities eller services direkt.
- Använd allowlistade systemverktyg genom native `pkexec`; ta bort egna policyfiler som inte faktiskt binder en operation till ett särskilt helper-kontrakt.
- Utöka arkitekturgrinden så att den blockerar indirekta UI→utility→subprocess-vägar och mutation utanför godkända executors.
- Engelska förblir enda språk i v27 enligt valt scope.

## Test- och leveransplan

- Höj total täckningsgräns till 90 % och kräv 95 % för plattformsdetektering, Action Center och privilegierade gränser.
- Testa varje åtgärd för fresh preflight, stängda parametrar, samtidighetslås, avvisad autentisering, timeout, avbrott, oberoende verifiering och exakt recovery-metadata.
- Kvalificera Fedora 43 och 44; Fedora 45 hålls preview tills final release finns.
- Kör verklig installation och huvudresa på GNOME Workstation, KDE, Silverblue och Kinoite. Kör start-, navigation-, update-, plan- och support-smoke på övriga officiella Fedora-desktops och Atomic-varianter. Fedora erbjuder idag både många klassiska spins och flera Atomic-desktops, vilket motiverar capability-first i stället för desktop-paritet. [Fedora Spins](https://fedoraproject.org/en/spins/), [Fedora Atomic Desktops](https://www.fedoraproject.org/atomic-desktops/)
- Verifiera x86_64 fullt och aarch64 för paketparsing, installation, start och kärnflöden.
- Testa saknad Flatpak/fwupd/polkit-agent, icke-admin, okänd/bootc-backend, annan Flatpak-remote, maskin utan batteri och localeoberoende kommandoutdata.
- UI-matris: ljust/mörkt, 100–200 % text, 1024×768 till ultrawide, Tab/Shift+Tab, Enter/Space, Escape, fokusåterställning och statusannonsering.
- Genomför manuella Orca-resor på GNOME och KDE samt verkliga Polkit-, reboot- och rpm-ostree-rollbackflöden. De förblir `unverified` tills de körts.
- Säkerställ att borttagna plugins, rutter, paket, imports, dokumentationslänkar och legacy-mutationer verkligen är frånvarande.
- Leverera som fasindelade ändringar: publiceringssanning → produktkapning → plattformsprofil → kärnresor → fysisk kvalificering. Ingen commit, push eller ny release ingår utan separat uttrycklig auktorisering.

## Antaganden

- “Alla Fedora-användare” betyder alla officiella Fedora-desktopvarianter för den desktopneutrala underhållskärnan, inte identisk desktop-tweaking på varje miljö.
- Server, CoreOS, IoT och rena headless-installationer ligger utanför v27.
- Säkerhetsmodellen, explicit användarstart, Traditional/Atomic-separation, ingen automatisk reboot/retry/rollback och oberoende resultatverifiering ska bevaras.
- Första genomförandesteg är att rätta den felaktiga publika v26-statusen och därefter skapa v27:s produkt- och borttagningskontrakt.
