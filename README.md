# Anker

Marktsignaal, Nederlands nieuws en twee dagelijkse lessen. Op je beginscherm, met echte meldingen.

Thema van de reeks: **Vertrouwen.** 's Ochtends bouw je het (een verhuurkantoor draait erop), 's avonds lees je het (hoe mensen werken), overdag zie je het bewegen (markten en instituties).

---

## Wat je krijgt

**Signaal** — leest doorlopend NOS, NU.nl, DNB, ECB, de Fed, CBS, MarketWatch, CNBC en een reeks Google News-zoekopdrachten op woningmarkt, huurmarkt, hypotheekrente, ECB-rente, goud, crypto en conflict. Ontdubbelt, sorteert op tijd, deelt in zes categorieën in en markeert zware berichten. Per bericht een samenvatting en een blok "wat dit betekent".

**Lessen** — 08:00 een les over het runnen van een luxe verhuurmakelaarskantoor, 22:00 een les over hoe mensen werken. 90 onderwerpen per kant, dus een halfjaar zonder herhaling, plus een archief.

**Meldingen** — twee routes, zie hieronder.

---

## Stap 1 · Online zetten (10 minuten, gratis)

De app moet op een https-adres staan. Een bestand op je telefoon kan geen homescreen-app worden.

1. Maak op github.com een repository. Naam bijvoorbeeld `anker`. Zet hem op **Public**.
2. Upload alle bestanden uit deze map, met de mappen erbij (`icons/`, `scripts/`, `state/`).
   De map `.github` is verborgen en gaat bij slepen meestal niet mee. Maak die handmatig via
   **Add file → Create new file** en typ als naam `.github/workflows/anker.yml`, plak dan de
   inhoud van dat bestand.
3. Ga naar **Settings → Pages**. Source `Deploy from a branch`, branch `main`, map `/ (root)`. Opslaan.
4. Na een minuut of twee staat je app op `https://JOUWNAAM.github.io/anker/`.

### Waarom Public en niet Private

Twee harde redenen:

- **Pages werkt niet op een private repo** zonder betaald plan. Geen URL betekent geen app op je beginscherm.
- **Actions-minuten zijn beperkt op private repos**: 2000 per maand. Elke tien minuten draaien is
  ruim 4300 runs, dus je zit er binnen twee weken doorheen. Op een public repo zijn Actions-minuten
  onbeperkt.

Wat er dan zichtbaar is: deze code, je lijst RSS-feeds, en `state/seen.json` met hashes en
tijdstempels. Geen namen, geen dossiers, geen sleutels. **Je API-sleutel en je ntfy-topic gaan in
Secrets** (stap 3 en 4) en die zijn versleuteld, ook in een public repo. Zet nooit een sleutel
rechtstreeks in een bestand.

Wil je toch per se privé blijven: zet de app op [netlify.com/drop](https://app.netlify.com/drop) voor
de https-URL, en houd de GitHub-repo privé alleen voor de meldingen. Reken dan wel op de
minutenlimiet, of zet het interval in `anker.yml` op `*/30` in plaats van `*/10`.

## Stap 2 · Op je beginscherm

Open het adres in **Safari** (niet Chrome, op iOS werkt het alleen via Safari), tik op deel → **Zet op beginscherm**. Vanaf nu opent Anker fullscreen zonder browserbalk. Dit is ook de voorwaarde voor meldingen op iOS.

Open de app, ga naar Instellingen, tik **Meldingen aanzetten** en accepteer.

## Stap 3 · Duiding door Claude (optioneel)

Zonder sleutel toon je koppen met een vaste duiding per categorie. Met sleutel schrijft Claude per bericht een samenvatting op jouw lengte en genereert hij de dagelijkse lessen.

1. Haal een API-sleutel op console.anthropic.com en zet er een uitgavenlimiet op.
2. Plak hem in Instellingen. Hij blijft op je toestel en gaat rechtstreeks naar Anthropic.

Kosten met Sonnet, tien berichten per verversing en twee lessen per dag: grofweg een paar euro per maand. Haiku is een stuk goedkoper en voor koppen prima.

## Stap 4 · Echte meldingen, ook met de app dicht

Dit is het deel dat de app zelf niet kan. iOS voert geen achtergrondcode uit voor webapps, dus moet een server het duwen.

1. Installeer **ntfy** uit de App Store. Gratis.
2. Bedenk een topicnaam die niemand raadt, bijvoorbeeld `anker-tim-7k2m9x`. Iedereen die de naam kent kan meelezen, dus maak hem lang en willekeurig.
3. Abonneer je in de app op dat topic. Zet meldingen aan.
4. In je GitHub-repo: **Settings → Secrets and variables → Actions → New repository secret**
   - `NTFY_TOPIC` = je topicnaam
   - `ANTHROPIC_API_KEY` = je sleutel (alleen als je duiding wilt)
5. Ga naar het tabblad **Actions** en zet workflows aan als GitHub daarom vraagt.

Vanaf dat moment: elke tien minuten nieuwscontrole, 08:00 ochtendles, 22:00 avondles, ook als je telefoon in je zak zit.

**Eerste run duwt niets.** Het script vult eerst zijn geheugen, anders krijg je vierhonderd meldingen tegelijk. Vanaf de tweede run gaat het lopen.

Handmatig testen: Actions → Anker → **Run workflow** → kies `lesson-morning`. Die negeert de tijdcontrole.

---

## Aanpassen

**Bronnen.** In de app onder Instellingen voor je telefoon, in `feeds.txt` voor de server. Houd beide gelijk. Formaat: één feed per regel, optioneel `|CATEGORIE` erachter. Categorieën: `MARKT`, `NL WONEN`, `GEOPOLITIEK`, `MACRO`, `NEDERLAND`, `CRYPTO`.

Een eigen zoekopdracht toevoegen gaat het makkelijkst via Google News:

```
https://news.google.com/rss/search?q=ZOEKTERM+when:2d&hl=nl&gl=NL&ceid=NL:nl|MACRO
```

**Hoeveel meldingen.** In `.github/workflows/anker.yml` staat `MAX_PUSH: "6"`. Dat is de bovengrens per run; de rest krijg je als één samenvattende melding. Wil je alleen het zware nieuws: zet in de app "Alleen bij hoge impact" aan, of pas de lijst `HIGH` aan in `scripts/anker_watch.py`.

**Lesonderwerpen.** Staan in `curriculum.json`, negentig per kant, gegroepeerd in modules. Voeg regels toe of gooi ze eruit. De volgorde volgt de dag van het jaar, dus na een wijziging schuift de reeks op. De tien volledig uitgeschreven lessen per kant zijn de terugval als er geen API-sleutel is.

**Tijden.** GitHub-cron draait op UTC. De workflow start op twee uren en het script controleert zelf de Amsterdamse klok, zodat zomer- en wintertijd allebei goed gaan. Wil je 07:00 in plaats van 08:00, pas dan zowel de cron-regel als `want = 8` in `run_lesson` aan.

---

## Waar het misgaat

**Lege lijst in de app.** Feeds staan geen directe browsertoegang toe, dus de app gaat via publieke proxies. Die zijn soms traag of even weg. De server-route (stap 4) heeft dat probleem niet. Werkt het lang niet, haal dan de zwaarste bronnen weg.

**Wel meldingen van ntfy, niets van de app.** Dat klopt en is niet erg: de app is de leesomgeving, ntfy is het alarm. Zolang je Anker niet openhebt, doet je telefoon niets voor de PWA.

**Actions stopt na een tijd.** GitHub pauzeert geplande workflows in repositories waar zestig dagen niets gebeurt. Eén commit zet hem weer aan. De workflow schrijft zijn status terug naar `state/seen.json`, dus in de praktijk blijft hij vanzelf actief.

**Cron loopt achter.** Op de gratis laag is `*/10` een intentie, geen garantie. In de praktijk krijg je vijf tot vijftien minuten. "De eerste seconde" bestaat niet zonder betaalde streaming-feed; dit is de dichtstbijzijnde gratis benadering.

---

## Wat er in de melding staat

```
MACRO · De Nederlandsche Bank
DNB verplaatst 86 ton goud van New York en Ottawa naar Londen

[samenvatting in jouw ingestelde lengte]

WAT DIT BETEKENT
[twee tot drie zinnen, toegespitst op de categorie]
```

Tikken opent de bron. Alles blijft in het archief van de app staan.
