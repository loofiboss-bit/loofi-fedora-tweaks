# V28 “Ease” — tydligare, snabbare och mer tillförlitlig Fedora-vardag

## Bedömning och mål

**V28 bör förfina den befintliga underhållskärnan genom bättre återkoppling, enklare arbetsflöden och verifierad användbarhet på fler Fedora-miljöer.**

V27.0.1 har redan fem huvudområden, granskade systemändringar och separat resultatkontroll. Däremot återstår fysisk skrivbordskvalificering och det uppskjutna täckningsmålet. [V27:s kvalificeringsrapport](https://github.com/loofiboss-bit/loofi-fedora-tweaks/blob/4860aea3b8fe07fe7fedcf7d8b3160eba2d48d30/docs/reports/V27_RELEASE_PUBLICATION.md).

Planeringen bygger på aktuell `master` vid `4860aea`, kodgranskning och 91 godkända riktade tester i isolerad miljö. Full testsvit och fysisk UI-granskning har inte genomförts här.

Målgruppen är nybörjare och vana Fedora-användare på KDE/GNOME, med traditionell Fedora och rpm-ostree-baserad Atomic. Gränssnittet förblir engelskt. Samma arbetsflöden används för alla; tekniska detaljer visas vid behov.

## Prioriterade förändringar

### P0 — korrekta besked och plattformsval

- **Rätta uppdateringskontrollens backendval.** Den kan i dag välja `rpm-ostree` på ett `bootc`-system. Använd `PlatformProfile.deployment_backend` genom hela flödet. DNF och rpm-ostree får egna vägar; bootc-systemuppdateringar får tydlig manuell vägledning i v28. Okänd backend får aldrig gissas.
- **Skilj historikfel från tom historik.** Läsfel ska visa att historiken inte kunde hämtas, med återförsök. Delvis läsbara uppgifter ska behållas och märkas. Ingen grön ”No recent changes” efter ett lagringsfel.
- **Samla Fedora-stödpolicyn.** GUI, CLI, uppdateringar och Changes ska använda samma klassning av stödd version, förhandsversion och okänd version. Utgångspunkten är Fedora 43/44; Fedora 45 förblir förhandsversion tills separat kvalificering är klar.
- **Isolera tester från användarens dator.** Gemensam testuppsättning ska använda temporära XDG-kataloger och mockade systemanrop. Ett befintligt test föll med lokal sparad status men passerade i isolering.

### P1 — finslipa de dagliga arbetsflödena

- **Uppdateringar:** varje källa visar egen kontrollstatus och resultat så snart den är klar. Tillåt högst tre samtidiga läskontroller, avbrytning och återförsök för en enskild källa. En långsam systemkontroll får inte dölja färdiga Flatpak-resultat.
- **Kortare väg till granskning:** ersätt källans välj–klicka-igen-flöde med en tydlig `Review updates`-knapp. Visa den när färska uppdateringar finns. Behåll separat granskning, bekräftelse, körning och verifiering i Changes.
- **Begriplig Changes-vy:** visa vad som ändras, omfattning, behörighetsbehov, omstart och återställningsmöjlighet före teknisk utdata. Resultatet ska förklara vad som kontrollerades och vad användaren behöver göra härnäst.
- **Sammanhängande språk:** använd huvudområdenas aktuella namn i onboarding, knappar, hjälp och felmeddelanden. Återanvänd befintlig återupptagbar introduktion och detaljutfällning.
- **Bättre sökning:** bygg åtgärdssökningen från samma aktiva katalog som Changes. Lägg uppgiftsord som `free disk space`, `updates` och `slow system`; matcha sökord oberoende av ordningsföljd. Sökresultat öppnar rätt sida eller granskning.
- **Användbar historik:** lägg filtrering efter resultat och `Load more` i omgångar om 25 poster. Behåll urval och position när användaren återvänder från en körningsdetalj.

### P1 — tillgänglighet, prestanda och underhåll

- Förfina befintliga komponenter och designtokens för tydlig fokusmarkering, textbrytning, kontrast och konsekvent knapphierarki. Status ska uttryckas med text och ikon.
- Säkerställ att centrala flöden fungerar med tangentbord, skärmläsare och 100–200 procent skalning. Sidopanelen ska kunna kollapsa och kontroller förbli åtkomliga på små skärmar.
- Mät starttid, minne och navigeringsrespons med befintligt benchmark. Behåll lat inläsning och frånvaro av automatiska bakgrundskontroller.
- Kartlägg pensionerade modulers import- och migreringsberoenden och ta bort oanvänd kod från både källträd och paket. Behåll endast dokumenterat nödvändiga läsare och migreringar för sparade användardata.

## Gränssnitt och datakontrakt

- Behåll fem huvudområden, nuvarande GUI/CLI och Changes som enda auktoritet för systemändringar.
- Utöka uppdateringstjänsten med källval, delresultat och avbrytning. Händelser knyts till ett kontroll-ID så att äldre svar inte skriver över nyare resultat.
- Spara färdiga källresultat atomiskt. Avbrutna eller misslyckade kontroller får inte ersätta tidigare observationer med ”inga uppdateringar”. Äldre cache utan säker backendkoppling behandlas som inaktuell.
- Historiktjänsten returnerar poster, lässtatus och fortsättningsmarkör; UI behöver inte tolka undantag som tomma resultat.
- Befintliga CLI-kommandon och dokumenterade JSON-kontrakt bevaras. Eventuella schemaändringar versionshanteras och migrering från v27 testas.
- Bootc och okända miljöer får använda kontroller vars förmågor är fastställda; systemuppdatering och återställning erbjuds endast när rätt backend stöds.

## Verifiering och acceptans

| Område | Krav för färdig v28 |
|---|---|
| Plattformsval | Tabelltester för DNF, rpm-ostree, bootc och okänd backend, inklusive flera installerade verktyg. Ingen korskoppling mellan backends. |
| Uppdateringar | Testa offline, timeout, saknade verktyg, delresultat, avbrytning, återförsök, navigering under kontroll och sena svar. |
| Historik och tillstånd | Testa oläsbara och skadade filer, delvis tillgänglig historik, fler än 25 poster samt uppgradering från v27. |
| Användarflöden | Första kontroll, uppdatering, felsökning, lagringsstädning och återställningsgranskning fungerar genom hela flödet med tangentbord. |
| Riktiga installationer | Fedora 43/44 KDE och GNOME samt motsvarande rpm-ostree-miljöer: ren installation, uppgradering från v27 och avinstallation med bevarade användardata. |
| Behörighet och omstart | Godkänd, nekad och avbruten Polkit-dialog; faktisk uppdatering, omstart och efterföljande verifiering. |
| Tillgänglighet | Dokumenterade KDE/GNOME-sessioner med Orca, fokusåtergång, ljus/mörk presentation och 100–200 procent skalning. |
| Prestanda | Synlig återkoppling inom 100 ms vid startad uppgift. Starttid och vilominnes median får inte försämras mer än 10 procent mot v27 på samma dokumenterade referensmiljö. |
| Kod och paket | Full `just verify`, produktkontrakt, paketeringskontroll, RPM/sdist-byggen och dokumentationskontroll passerar. Minst 90 procent täckning av kvarvarande produktkod utan nya undantag för att nå siffran. |

Komplettera med fem observerade användarsessioner, minst två med Fedora-nybörjare. Minst fyra av fem ska kunna genomföra kontroll, uppdateringsgranskning och hitta resultat utan handledning. Alla återkommande missförstånd åtgärdas före slutkvalificering.

Fysisk kvalificering är ett lanseringskrav för de miljöer som marknadsförs som stödda. Offscreen-tester ersätter inte detta.

## Genomförande och avgränsningar

Genomför i ordning: **P0-korrekthet och testisolering → uppdateringsflöde och historik → språk, sökning och tillgänglighet → kodrensning och full kvalificering.**

- Planera första nya utgåvan som **v28.0.1 “Ease”**. Historiska `v28.0.0` bevaras; kontrollera åter att målversionen är ledig innan versionsändring.
- Dokumentera planen och implementationsuppgifterna på engelska enligt projektets befintliga plan-/arkitektur-/taskformat.
- Behåll engelska, befintligt ramverk och RPM-distribution. Inga nya specialistpaket, automatiska optimeringsprofiler, bakgrundstjänster eller nya beroenden ingår.
- Git-ändringar, publicering och ändringar på användarens värdsystem kräver separat uttryckligt uppdrag.
