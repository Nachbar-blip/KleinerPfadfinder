'use strict';
const fs = require('fs');
const path = require('path');
const FILE = path.join(__dirname, 'berufe.json');

const fixes = {
  gaertner_obstbau: { tags: ['pflanze_bestimmen_pflegen', 'ernte_verarbeiten', 'praezisionsarbeit_hand'] },
  gaertner_garten_landschaftsbau: { tags: ['garten_anlegen', 'pflanze_bestimmen_pflegen', 'mauer_errichten'] },
  schuhmacher: { tags: ['stoff_verarbeiten', 'praezisionsarbeit_hand', 'kunde_beraten_verkaufen'], kategorien: ['handwerk_material'] },
  medientechnologe_druck: { tags: ['maschine_bedienen', 'maschine_warten_reparieren', 'praezisionsarbeit_hand'] },
  buchbinder: { tags: ['praezisionsarbeit_hand', 'stoff_verarbeiten', 'maschine_bedienen'] },
  medientechnologe_druckverarbeitung: { tags: ['maschine_bedienen', 'maschine_warten_reparieren', 'praezisionsarbeit_hand'] },
  medientechnologe_siebdruck: { tags: ['maschine_bedienen', 'praezisionsarbeit_hand', 'stoff_verarbeiten'] },
  orthopaedieschuhmacher: { tags: ['praezisionsarbeit_hand', 'patient_untersuchen', 'mensch_beraten_begleiten'] },
  fachkraft_kueche: { tags: ['speise_zubereiten', 'lebensmittel_herstellen', 'maschine_bedienen'] },
  nageldesigner_kosmet: { tags: ['praezisionsarbeit_hand', 'kunde_beraten_verkaufen', 'mensch_beraten_begleiten'] },
  glasmacher: { tags: ['glas_bearbeiten', 'praezisionsarbeit_hand', 'maschine_bedienen'] }
};

const arr = JSON.parse(fs.readFileSync(FILE, 'utf8'));
let n = 0;
for (const b of arr) {
  if (fixes[b.id]) {
    Object.assign(b, fixes[b.id]);
    b.needs_review = false;
    n++;
  }
}
fs.writeFileSync(FILE, JSON.stringify(arr, null, 2), 'utf8');
console.log(`${n} Berufe korrigiert. needs_review jetzt:`, arr.filter(b => b.needs_review).length);
