<?php
// foerderer-antrag.php — Formular + Vorschau + Datenbankanlage
require_once 'config_foerderer.php';

$fehler  = [];
$preview = false;
$data    = [];

// ── Schritt 2: Vorschau nach Formular-Submit ────────────────────────────────
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['action']) && $_POST['action'] === 'preview') {

  $data = [
    'firma'        => trim($_POST['firma']        ?? ''),
    'beschreibung' => trim($_POST['beschreibung'] ?? ''),
    'website'      => trim($_POST['website']      ?? ''),
    'kategorie'    => trim($_POST['kategorie']    ?? ''),
    'email'        => trim($_POST['email']        ?? ''),
    'betrag'       => (float) ($_POST['betrag']   ?? 50),
  ];

  // Validierung
  if (strlen($data['firma']) < 2)        $fehler[] = 'Firmenname ist zu kurz.';
  if (strlen($data['beschreibung']) < 20) $fehler[] = 'Beschreibung zu kurz (min. 20 Zeichen).';
  if (!filter_var($data['email'], FILTER_VALIDATE_EMAIL)) $fehler[] = 'E-Mail-Adresse ungültig.';
  if ($data['betrag'] < 50)              $fehler[] = 'Mindestbetrag ist 50 €.';

  // Logo-Upload
  $logo_datei = '';
  if (isset($_FILES['logo']) && $_FILES['logo']['error'] === UPLOAD_ERR_OK) {
    $mime_ok = in_array($_FILES['logo']['type'], ['image/jpeg','image/png','image/webp','image/svg+xml']);
    $size_ok = $_FILES['logo']['size'] <= 800 * 1024; // 800 KB
    if (!$mime_ok) $fehler[] = 'Logo: nur JPG, PNG, WebP oder SVG erlaubt.';
    if (!$size_ok) $fehler[] = 'Logo: max. 800 KB.';
    if ($mime_ok && $size_ok) {
      if (!is_dir(UPLOAD_DIR)) mkdir(UPLOAD_DIR, 0755, true);
      $ext       = strtolower(pathinfo($_FILES['logo']['name'], PATHINFO_EXTENSION));
      $tmp_name  = 'prev_' . bin2hex(random_bytes(8)) . '.' . $ext;
      move_uploaded_file($_FILES['logo']['tmp_name'], UPLOAD_DIR . $tmp_name);
      $logo_datei = $tmp_name;
    }
  }

  if (empty($fehler)) {
    $preview      = true;
    $data['logo'] = $logo_datei;
  }
}

// ── Schritt 3: In DB speichern + zu PayPal weiterleiten ────────────────────
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['action']) && $_POST['action'] === 'checkout') {
  $data = [
    'firma'        => trim($_POST['firma']        ?? ''),
    'beschreibung' => trim($_POST['beschreibung'] ?? ''),
    'website'      => trim($_POST['website']      ?? ''),
    'kategorie'    => trim($_POST['kategorie']    ?? ''),
    'email'        => trim($_POST['email']        ?? ''),
    'betrag'       => (float) ($_POST['betrag']   ?? 50),
    'logo'         => trim($_POST['logo_datei']   ?? ''),
  ];

  $token = omn_token();
  $expires = date('Y-m-d', strtotime('+1 year'));

  $db = omn_db();
  $st = $db->prepare("INSERT INTO foerderer
    (token, firma, beschreibung, website, kategorie, email, betrag, logo_datei, expires_at)
    VALUES (?,?,?,?,?,?,?,?,?)");
  $st->execute([
    $token,
    $data['firma'],
    $data['beschreibung'],
    $data['website'],
    $data['kategorie'],
    $data['email'],
    $data['betrag'],
    $data['logo'],
    $expires,
  ]);
  $id = $db->lastInsertId();

  // Zum PayPal-Checkout
  $paypal_base = PAYPAL_SANDBOX
    ? 'https://www.sandbox.paypal.com/cgi-bin/webscr'
    : 'https://www.paypal.com/cgi-bin/webscr';

  $params = http_build_query([
    'cmd'           => '_xclick',
    'business'      => PAYPAL_EMAIL,
    'item_name'     => 'OpenMycoNet Förderer-Eintrag: ' . $data['firma'],
    'item_number'   => 'FOERDERER-' . $id,
    'amount'        => number_format($data['betrag'], 2, '.', ''),
    'currency_code' => 'EUR',
    'no_shipping'   => '1',
    'notify_url'    => PAYPAL_IPN_URL,
    'return'        => PAYPAL_RETURN . '?token=' . $token,
    'cancel_return' => PAYPAL_CANCEL,
    'custom'        => $token,
    'charset'       => 'UTF-8',
    'lc'            => 'DE',
  ]);

  header('Location: ' . $paypal_base . '?' . $params);
  exit;
}

// ── Betrag-Optionen ─────────────────────────────────────────────────────────
$betrag_optionen = [50, 100, 200, 500];
$kategorien = [
  'Pilzzucht & Mykologie',
  'Landwirtschaft & Gartenbau',
  'Forstwirtschaft & Waldschutz',
  'Wissenschaft & Forschung',
  'Bildung & Medien',
  'Nachhaltige Produkte',
  'Technologie & Software',
  'Sonstiges',
];
?>
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title id="page-title">Förderer werden – OpenMycoNet</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,500;1,400&family=JetBrains+Mono:wght@400;500&family=Lora:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #024530; --bg2: #013826; --bg3: rgba(0,0,0,0.22);
  --text: #e8f5e0; --text2: #a0c8a0; --text3: #5a8a6a;
  --accent: #6ee87e; --accent3: #0a7050;
  --amber: #f0b84a; --amber2: #d4a030; --amber3: rgba(200,136,42,0.12);
  --border: #0a6040;
  --font-body: 'Playfair Display', Georgia, serif;
  --font-ui: 'Lora', Georgia, serif;
  --font-mono: 'JetBrains Mono', monospace;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--text); font-family: var(--font-ui); line-height: 1.75; min-height: 100vh; }
a { color: var(--accent); }

nav { position: fixed; top: 0; left: 0; right: 0; z-index: 100; display: flex; justify-content: space-between; align-items: center; padding: 1rem clamp(1.5rem,5vw,5rem); background: rgba(2,69,48,0.97); border-bottom: 1px solid var(--border); }
.nav-logo { font-family: var(--font-mono); font-size: 0.9rem; color: var(--accent); letter-spacing: 0.1em; text-transform: uppercase; text-decoration: none; }
.nav-logo span { color: var(--amber); }
.back-link { font-family: var(--font-mono); font-size: 0.75rem; color: #00e5e5; letter-spacing: 0.08em; text-transform: uppercase; text-decoration: none; border-bottom: 1px solid #00e5e5; padding-bottom: 2px; }

.page { max-width: 720px; margin: 0 auto; padding: 7rem 2rem 5rem; }
.page-tag { font-family: var(--font-mono); font-size: 0.68rem; color: var(--amber2); letter-spacing: 0.25em; text-transform: uppercase; margin-bottom: 1rem; display: flex; align-items: center; gap: 10px; }
.page-tag::before { content: ''; display: inline-block; width: 24px; height: 1px; background: var(--amber2); }
h1 { font-family: var(--font-body); font-size: clamp(1.8rem,4vw,2.5rem); font-weight: 400; color: #fff; margin-bottom: 2rem; line-height: 1.2; }
h1 em { font-style: italic; color: var(--accent); }

.form-group { margin-bottom: 1.4rem; }
label { display: block; font-family: var(--font-mono); font-size: 0.72rem; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text2); margin-bottom: 0.5rem; }
input[type=text], input[type=email], input[type=url], textarea, select {
  width: 100%; padding: 0.75rem 1rem;
  background: rgba(0,0,0,0.28); border: 1px solid var(--border);
  color: var(--text); font-family: var(--font-ui); font-size: 1rem;
  outline: none; transition: border-color 0.2s;
}
input:focus, textarea:focus, select:focus { border-color: var(--accent); }
textarea { resize: vertical; min-height: 100px; }
select option { background: #013826; }

.betrag-grid { display: flex; flex-wrap: wrap; gap: 0.75rem; margin-bottom: 0.5rem; }
.betrag-btn {
  padding: 0.6rem 1.4rem; border: 1px solid var(--border);
  background: var(--bg3); color: var(--text2);
  font-family: var(--font-mono); font-size: 0.85rem; cursor: pointer;
  transition: all 0.2s;
}
.betrag-btn.active, .betrag-btn:hover { border-color: var(--amber); color: var(--amber); background: var(--amber3); }
input[type=number] { width: 140px; }

.logo-upload { border: 1px dashed var(--border); padding: 1.5rem; text-align: center; cursor: pointer; transition: border-color 0.2s; position: relative; }
.logo-upload:hover { border-color: var(--accent); }
.logo-upload input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.logo-upload-label { font-family: var(--font-mono); font-size: 0.75rem; color: var(--text3); }
#logo-preview { max-height: 80px; max-width: 200px; margin-top: 0.75rem; display: none; }

.fehler-box { background: rgba(200,40,40,0.15); border: 1px solid #c82828; padding: 1rem 1.2rem; margin-bottom: 1.5rem; font-size: 0.9rem; }
.fehler-box ul { padding-left: 1.2rem; }

.btn { display: inline-block; padding: 0.75rem 2rem; font-family: var(--font-mono); font-size: 0.8rem; letter-spacing: 0.1em; text-transform: uppercase; border: 1px solid var(--border); cursor: pointer; transition: all 0.2s; text-decoration: none; }
.btn-green { background: var(--accent3); color: #fff; border-color: var(--accent3); }
.btn-green:hover { background: #3a9e5a; border-color: #3a9e5a; }
.btn-amber { background: transparent; color: var(--amber); border-color: var(--amber2); }
.btn-amber:hover { background: var(--amber3); }
.btn-ghost { background: transparent; color: var(--text2); }
.btn-ghost:hover { border-color: var(--text2); color: var(--text); }

/* ── Vorschau-Karte ── */
.preview-card {
  background: var(--bg3); border: 1px solid var(--border);
  border-top: 3px solid var(--amber2);
  padding: 1.5rem; margin-bottom: 2rem;
}
.preview-card .preview-logo { max-height: 60px; max-width: 160px; margin-bottom: 1rem; display: block; }
.preview-card .preview-firma { font-family: var(--font-body); font-size: 1.3rem; color: #fff; margin-bottom: 0.4rem; }
.preview-card .preview-kat { font-family: var(--font-mono); font-size: 0.65rem; color: var(--amber2); letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 0.75rem; }
.preview-card .preview-desc { font-size: 0.95rem; color: var(--text2); line-height: 1.7; margin-bottom: 0.75rem; }
.preview-card .preview-web { font-family: var(--font-mono); font-size: 0.75rem; color: var(--accent); }

.hinweis { font-family: var(--font-mono); font-size: 0.7rem; color: var(--text3); line-height: 1.8; margin-top: 1rem; }

.fee-box { padding: 0.75rem 1rem; border: 1px solid var(--border); background: rgba(0,0,0,0.18); font-family: var(--font-mono); font-size: 0.75rem; color: var(--text2); margin-bottom: 1.5rem; }
.fee-box label { display: flex; align-items: flex-start; gap: 10px; cursor: pointer; text-transform: none; letter-spacing: 0; font-size: 0.8rem; }
.fee-box input[type=checkbox] { margin-top: 3px; accent-color: var(--accent); flex-shrink: 0; }
</style>
</head>
<body>
<nav>
  <a class="nav-logo" href="index.html">Open<span>Myco</span>Net</a>
  <a class="back-link" href="foerderer.html" id="back-link">← Fördererseite</a>
</nav>

<div class="page">
  <div class="page-tag" id="page-tag">OpenMycoNet · Förderer werden</div>

<?php if ($preview): ?>
  <!-- ══ VORSCHAU ══════════════════════════════════════════════════════════ -->
  <h1 id="h1-preview">So sieht Ihr <em id="h1-preview-em">Eintrag</em> aus</h1>
  <p id="preview-intro" style="color:var(--text2); margin-bottom:2rem;">Prüfen Sie Ihren Eintrag. Bei Zahlung wird er genau so in der Fördererlist sichtbar.</p>

  <div class="preview-card">
    <?php if ($data['logo']): ?>
      <img src="<?= htmlspecialchars(UPLOAD_URL . $data['logo']) ?>" class="preview-logo" alt="Logo">
    <?php endif; ?>
    <div class="preview-firma"><?= htmlspecialchars($data['firma']) ?></div>
    <div class="preview-kat"><?= htmlspecialchars($data['kategorie']) ?></div>
    <div class="preview-desc"><?= nl2br(htmlspecialchars($data['beschreibung'])) ?></div>
    <?php if ($data['website']): ?>
      <div class="preview-web">🌐 <?= htmlspecialchars($data['website']) ?></div>
    <?php endif; ?>
  </div>

  <!-- Transaktionskosten-Option -->
  <div class="fee-box">
    <label>
      <input type="checkbox" id="cover-fees" onchange="updateFee()">
      <span>
        <span id="fee-label-text">Transaktionskosten übernehmen</span>:
        <strong id="fee-amt" style="color:var(--amber);">+<?= number_format($data['betrag'] * 0.0249 + 0.35, 2, ',', '') ?> €</strong>
        → Gesamt: <strong id="fee-total" style="color:var(--accent);"><?= number_format($data['betrag'] + $data['betrag'] * 0.0249 + 0.35, 2, ',', '') ?> €</strong>
      </span>
    </label>
  </div>

  <!-- Checkout-Formular -->
  <form method="post" action="foerderer-antrag.php">
    <input type="hidden" name="action"       value="checkout">
    <input type="hidden" name="firma"        value="<?= htmlspecialchars($data['firma']) ?>">
    <input type="hidden" name="beschreibung" value="<?= htmlspecialchars($data['beschreibung']) ?>">
    <input type="hidden" name="website"      value="<?= htmlspecialchars($data['website']) ?>">
    <input type="hidden" name="kategorie"    value="<?= htmlspecialchars($data['kategorie']) ?>">
    <input type="hidden" name="email"        value="<?= htmlspecialchars($data['email']) ?>">
    <input type="hidden" name="logo_datei"   value="<?= htmlspecialchars($data['logo']) ?>">
    <input type="hidden" name="betrag"       id="betrag-hidden" value="<?= $data['betrag'] ?>">

    <div style="display:flex; gap:1rem; flex-wrap:wrap;">
      <button type="submit" class="btn btn-amber" style="font-size:0.85rem; padding:0.85rem 2rem;">
        <span id="pay-btn-label">💳 Jetzt zahlen —</span> <span id="pay-label"><?= number_format($data['betrag'], 2, ',', '') ?> €</span> via PayPal
      </button>
      <a href="foerderer-antrag.php" class="btn btn-ghost" id="btn-edit">← Eintrag bearbeiten</a>
    </div>
    <p id="pay-note" class="hinweis" style="margin-top:1rem;">Nach erfolgreicher Zahlung wird Ihr Eintrag innerhalb von Minuten sichtbar. Sie erhalten eine Rechnung per E-Mail und als direkten Download.</p>
  </form>

  <script>
  var baseAmt = <?= $data['betrag'] ?>;
  function updateFee() {
    var checked = document.getElementById('cover-fees').checked;
    var fee   = Math.round((baseAmt * 0.0249 + 0.35) * 100) / 100;
    var total = Math.round((baseAmt + fee) * 100) / 100;
    var final = checked ? total : baseAmt;
    document.getElementById('fee-amt').textContent   = '+' + fee.toFixed(2).replace('.',',') + ' €';
    document.getElementById('fee-total').textContent = total.toFixed(2).replace('.',',') + ' €';
    document.getElementById('pay-label').textContent = final.toFixed(2).replace('.',',') + ' €';
    document.getElementById('betrag-hidden').value   = final.toFixed(2);
  }
  </script>

<?php else: ?>
  <!-- ══ FORMULAR ══════════════════════════════════════════════════════════ -->
  <h1 id="h1-form">Förderer <em id="h1-form-em">werden</em></h1>
  <p id="form-intro" style="color:var(--text2); margin-bottom:2rem; max-width:540px;">Gestalten Sie Ihren Eintrag — Sie sehen eine Vorschau bevor Sie zahlen. Keine Vorauszahlung, keine Verpflichtung.</p>

  <?php if (!empty($fehler)): ?>
  <div class="fehler-box">
    <ul><?php foreach ($fehler as $f): ?><li><?= htmlspecialchars($f) ?></li><?php endforeach; ?></ul>
  </div>
  <?php endif; ?>

  <form method="post" action="foerderer-antrag.php" enctype="multipart/form-data">
    <input type="hidden" name="action" value="preview">

    <div class="form-group">
      <label id="lbl-firma">Firmenname *</label>
      <input type="text" name="firma" value="<?= htmlspecialchars($_POST['firma'] ?? '') ?>" required maxlength="120" placeholder="Ihr Unternehmensname">
    </div>

    <div class="form-group">
      <label id="lbl-desc">Kurzbeschreibung * <span style="font-weight:400; text-transform:none; letter-spacing:0; color:var(--text3);">(20–300 Zeichen, erscheint im Eintrag)</span></label>
      <textarea name="beschreibung" required maxlength="300" placeholder="Was macht Ihr Unternehmen? Warum unterstützen Sie OpenMycoNet?"><?= htmlspecialchars($_POST['beschreibung'] ?? '') ?></textarea>
      <div style="font-family:var(--font-mono); font-size:0.65rem; color:var(--text3); margin-top:4px;"><span id="char-count">0</span> / 300</div>
    </div>

    <div class="form-group">
      <label id="lbl-website">Website</label>
      <input type="url" name="website" value="<?= htmlspecialchars($_POST['website'] ?? '') ?>" placeholder="https://www.beispiel.de">
    </div>

    <div class="form-group">
      <label id="lbl-kategorie">Kategorie *</label>
      <select name="kategorie" required>
        <option value="">— bitte wählen —</option>
        <?php foreach ($kategorien as $k): ?>
          <option value="<?= htmlspecialchars($k) ?>" <?= ($_POST['kategorie'] ?? '') === $k ? 'selected' : '' ?>>
            <?= htmlspecialchars($k) ?>
          </option>
        <?php endforeach; ?>
      </select>
    </div>

    <div class="form-group">
      <label id="lbl-logo">Logo <span style="font-weight:400; text-transform:none; letter-spacing:0; color:var(--text3);">(JPG, PNG, WebP oder SVG · max. 800 KB)</span></label>
      <div class="logo-upload" onclick="this.querySelector('input').click()">
        <input type="file" name="logo" accept="image/jpeg,image/png,image/webp,image/svg+xml" onchange="previewLogo(this)">
        <div class="logo-upload-label" id="logo-upload-label">📁 Logo hier ablegen oder klicken zum Auswählen</div>
        <img id="logo-preview" src="" alt="Vorschau">
      </div>
    </div>

    <div class="form-group">
      <label id="lbl-betrag">Jahresbeitrag * <span style="font-weight:400; text-transform:none; letter-spacing:0; color:var(--text3);">(mind. 50 €, frei wählbar)</span></label>
      <div class="betrag-grid">
        <?php foreach ($betrag_optionen as $b): ?>
          <button type="button" class="betrag-btn <?= ($b == 50) ? 'active' : '' ?>"
            onclick="setBetrag(<?= $b ?>, this)"><?= $b ?> €</button>
        <?php endforeach; ?>
      </div>
      <div style="display:flex; align-items:center; gap:0.5rem; margin-top:0.5rem;">
        <span style="font-family:var(--font-mono); font-size:0.8rem; color:var(--text3);">oder</span>
        <input type="number" name="betrag" id="betrag-input" value="50" min="50" step="1"
          oninput="clearBetragBtns()" style="width:120px;">
        <span style="font-family:var(--font-mono); font-size:0.8rem; color:var(--text3);">€</span>
      </div>
    </div>

    <div class="form-group">
      <label id="lbl-email">Ihre E-Mail-Adresse * <span style="font-weight:400; text-transform:none; letter-spacing:0; color:var(--text3);">(für Rechnung und Erneuerung)</span></label>
      <input type="email" name="email" value="<?= htmlspecialchars($_POST['email'] ?? '') ?>" required placeholder="ihre@email.de">
    </div>

    <button type="submit" class="btn btn-green" style="margin-top:0.5rem;" id="btn-submit">Vorschau anzeigen →</button>
    <p class="hinweis" id="hinweis-text">* Pflichtfelder · Keine Vorauszahlung · Zahlung erst nach Vorschau-Bestätigung</p>
  </form>
<?php endif; ?>
</div>

<script>
// Zeichen-Zähler
var ta = document.querySelector('textarea[name=beschreibung]');
if (ta) {
  function updateCount() { document.getElementById('char-count').textContent = ta.value.length; }
  ta.addEventListener('input', updateCount);
  updateCount();
}

// Logo-Vorschau
function previewLogo(input) {
  var prev = document.getElementById('logo-preview');
  if (input.files && input.files[0]) {
    var reader = new FileReader();
    reader.onload = function(e) { prev.src = e.target.result; prev.style.display = 'block'; };
    reader.readAsDataURL(input.files[0]);
  }
}

// Betrag-Buttons
function setBetrag(val, btn) {
  document.querySelectorAll('.betrag-btn').forEach(function(b){ b.classList.remove('active'); });
  btn.classList.add('active');
  document.getElementById('betrag-input').value = val;
}
function clearBetragBtns() {
  document.querySelectorAll('.betrag-btn').forEach(function(b){ b.classList.remove('active'); });
}
</script>

<script>
// ── Antrag-Übersetzungen ──────────────────────────────────────────────────
var ANTRAG_TRANS = {
  de: {
    page_title: 'Förderer werden – OpenMycoNet',
    back_link: '← Fördererseite',
    page_tag: 'OpenMycoNet · Förderer werden',
    h1_preview: 'So sieht Ihr',
    h1_preview_em: 'Eintrag',
    h1_form: 'Förderer',
    h1_form_em: 'werden',
    preview_intro: 'Prüfen Sie Ihren Eintrag. Bei Zahlung wird er genau so in der Fördererlist sichtbar.',
    form_intro: 'Gestalten Sie Ihren Eintrag — Sie sehen eine Vorschau bevor Sie zahlen. Keine Vorauszahlung, keine Verpflichtung.',
    fee_label: 'Transaktionskosten übernehmen',
    pay_btn_label: '💳 Jetzt zahlen —',
    pay_note: 'Nach erfolgreicher Zahlung wird Ihr Eintrag innerhalb von Minuten sichtbar. Sie erhalten eine Rechnung per E-Mail und als direkten Download.',
    lbl_firma: 'Firmenname *',
    lbl_desc: 'Kurzbeschreibung *',
    lbl_website: 'Website',
    lbl_kategorie: 'Kategorie *',
    lbl_logo: 'Logo',
    lbl_betrag: 'Jahresbeitrag *',
    lbl_email: 'Ihre E-Mail-Adresse *',
    logo_upload: '📁 Logo hier ablegen oder klicken zum Auswählen',
    btn_submit: 'Vorschau anzeigen →',
    btn_edit: '← Eintrag bearbeiten',
    hinweis: '* Pflichtfelder · Keine Vorauszahlung · Zahlung erst nach Vorschau-Bestätigung',
    betrag_hint: '(mind. 50 €, frei wählbar)',
    desc_hint: '(20–300 Zeichen, erscheint im Eintrag)',
    logo_hint: '(JPG, PNG, WebP oder SVG · max. 800 KB)',
    email_hint: '(für Rechnung und Erneuerung)',
    oder: 'oder',
  },
  en: {
    page_title: 'Become a Supporter – OpenMycoNet',
    back_link: '← Supporter page',
    page_tag: 'OpenMycoNet · Become a supporter',
    h1_preview: 'This is how your',
    h1_preview_em: 'listing',
    h1_form: 'Become a',
    h1_form_em: 'supporter',
    preview_intro: 'Review your listing. After payment it will appear exactly like this in the supporters list.',
    form_intro: 'Design your own listing — you see a preview before you pay. No advance payment, no obligation.',
    fee_label: 'Cover transaction fees',
    pay_btn_label: '💳 Pay now —',
    pay_note: 'After successful payment your listing will be visible within minutes. You will receive an invoice by email and as a direct download.',
    lbl_firma: 'Company name *',
    lbl_desc: 'Short description *',
    lbl_website: 'Website',
    lbl_kategorie: 'Category *',
    lbl_logo: 'Logo',
    lbl_betrag: 'Annual contribution *',
    lbl_email: 'Your email address *',
    logo_upload: '📁 Drop logo here or click to select',
    btn_submit: 'Show preview →',
    btn_edit: '← Edit listing',
    hinweis: '* Required fields · No advance payment · Payment only after preview confirmation',
    betrag_hint: '(min. €50, freely selectable)',
    desc_hint: '(20–300 characters, appears in listing)',
    logo_hint: '(JPG, PNG, WebP or SVG · max. 800 KB)',
    email_hint: '(for invoice and renewal)',
    oder: 'or',
  },
  nl: {
    page_title: 'Word partner – OpenMycoNet',
    back_link: '← Partnerpagina',
    page_tag: 'OpenMycoNet · Word partner',
    h1_preview: 'Zo ziet uw',
    h1_preview_em: 'vermelding',
    h1_form: 'Word',
    h1_form_em: 'partner',
    preview_intro: 'Bekijk uw vermelding. Na betaling verschijnt deze precies zo in de partnerslijst.',
    form_intro: 'Ontwerp uw eigen vermelding — u ziet een voorbeeld voordat u betaalt. Geen vooruitbetaling, geen verplichting.',
    fee_label: 'Transactiekosten dekken',
    pay_btn_label: '💳 Nu betalen —',
    pay_note: 'Na succesvolle betaling is uw vermelding binnen enkele minuten zichtbaar. U ontvangt een factuur per e-mail en als directe download.',
    lbl_firma: 'Bedrijfsnaam *',
    lbl_desc: 'Korte beschrijving *',
    lbl_website: 'Website',
    lbl_kategorie: 'Categorie *',
    lbl_logo: 'Logo',
    lbl_betrag: 'Jaarbijdrage *',
    lbl_email: 'Uw e-mailadres *',
    logo_upload: '📁 Logo hier neerzetten of klikken om te selecteren',
    btn_submit: 'Voorbeeld weergeven →',
    btn_edit: '← Vermelding bewerken',
    hinweis: '* Verplichte velden · Geen vooruitbetaling · Betaling pas na bevestiging voorbeeld',
    betrag_hint: '(min. €50, vrij te kiezen)',
    desc_hint: '(20–300 tekens, verschijnt in vermelding)',
    logo_hint: '(JPG, PNG, WebP of SVG · max. 800 KB)',
    email_hint: '(voor factuur en verlenging)',
    oder: 'of',
  },
  fr: {
    page_title: 'Devenir partenaire – OpenMycoNet',
    back_link: '← Page partenaires',
    page_tag: 'OpenMycoNet · Devenir partenaire',
    h1_preview: 'Voici votre',
    h1_preview_em: 'annonce',
    h1_form: 'Devenir',
    h1_form_em: 'partenaire',
    preview_intro: 'Vérifiez votre annonce. Après le paiement, elle apparaîtra exactement ainsi dans la liste des partenaires.',
    form_intro: 'Créez votre propre annonce — vous voyez un aperçu avant de payer. Pas de paiement anticipé, aucune obligation.',
    fee_label: 'Couvrir les frais de transaction',
    pay_btn_label: '💳 Payer maintenant —',
    pay_note: 'Après le paiement, votre annonce sera visible en quelques minutes. Vous recevrez une facture par e-mail et en téléchargement direct.',
    lbl_firma: 'Nom de l\'entreprise *',
    lbl_desc: 'Brève description *',
    lbl_website: 'Site web',
    lbl_kategorie: 'Catégorie *',
    lbl_logo: 'Logo',
    lbl_betrag: 'Cotisation annuelle *',
    lbl_email: 'Votre adresse e-mail *',
    logo_upload: '📁 Déposez le logo ici ou cliquez pour sélectionner',
    btn_submit: 'Afficher l\'aperçu →',
    btn_edit: '← Modifier l\'annonce',
    hinweis: '* Champs obligatoires · Pas de paiement anticipé · Paiement après confirmation de l\'aperçu',
    betrag_hint: '(min. 50 €, librement choisi)',
    desc_hint: '(20–300 caractères, apparaît dans l\'annonce)',
    logo_hint: '(JPG, PNG, WebP ou SVG · max. 800 Ko)',
    email_hint: '(pour la facture et le renouvellement)',
    oder: 'ou',
  },
  es: {
    page_title: 'Convertirse en patrocinador – OpenMycoNet',
    back_link: '← Página de patrocinadores',
    page_tag: 'OpenMycoNet · Convertirse en patrocinador',
    h1_preview: 'Así se verá su',
    h1_preview_em: 'entrada',
    h1_form: 'Convertirse en',
    h1_form_em: 'patrocinador',
    preview_intro: 'Revise su entrada. Tras el pago aparecerá exactamente así en la lista de patrocinadores.',
    form_intro: 'Diseñe su propia entrada — verá una vista previa antes de pagar. Sin pago anticipado, sin compromiso.',
    fee_label: 'Cubrir los costes de transacción',
    pay_btn_label: '💳 Pagar ahora —',
    pay_note: 'Tras el pago su entrada será visible en minutos. Recibirá una factura por correo electrónico y como descarga directa.',
    lbl_firma: 'Nombre de la empresa *',
    lbl_desc: 'Breve descripción *',
    lbl_website: 'Sitio web',
    lbl_kategorie: 'Categoría *',
    lbl_logo: 'Logotipo',
    lbl_betrag: 'Cuota anual *',
    lbl_email: 'Su dirección de correo *',
    logo_upload: '📁 Suelte el logo aquí o haga clic para seleccionar',
    btn_submit: 'Mostrar vista previa →',
    btn_edit: '← Editar entrada',
    hinweis: '* Campos obligatorios · Sin pago anticipado · Pago solo tras confirmación de vista previa',
    betrag_hint: '(mín. 50 €, libre elección)',
    desc_hint: '(20–300 caracteres, aparece en la entrada)',
    logo_hint: '(JPG, PNG, WebP o SVG · máx. 800 KB)',
    email_hint: '(para factura y renovación)',
    oder: 'o',
  },
};

function getLangAntrag() {
  var p = new URLSearchParams(window.location.search).get('lang');
  if (p && ANTRAG_TRANS[p]) return p;
  var s = localStorage.getItem('omn_lang');
  if (s && ANTRAG_TRANS[s]) return s;
  var bl = (navigator.language || 'de').split('-')[0].toLowerCase();
  return ANTRAG_TRANS[bl] ? bl : 'de';
}

function applyAntragTrans() {
  var lang = getLangAntrag();
  var T = ANTRAG_TRANS[lang];
  if (!T) return;

  function set(id, text) {
    var el = document.getElementById(id);
    if (el && text) el.textContent = text;
  }

  set('page-tag', T.page_tag);
  set('back-link', T.back_link);
  set('h1-preview', T.h1_preview + ' ');
  set('h1-preview-em', T.h1_preview_em);
  set('h1-form', T.h1_form + ' ');
  set('h1-form-em', T.h1_form_em);
  set('preview-intro', T.preview_intro);
  set('form-intro', T.form_intro);
  set('fee-label-text', T.fee_label);
  set('pay-btn-label', T.pay_btn_label);
  set('pay-note', T.pay_note);
  set('lbl-firma', T.lbl_firma);
  set('lbl-desc', T.lbl_desc);
  set('lbl-website', T.lbl_website);
  set('lbl-kategorie', T.lbl_kategorie);
  set('lbl-logo', T.lbl_logo);
  set('lbl-betrag', T.lbl_betrag);
  set('lbl-email', T.lbl_email);
  set('logo-upload-label', T.logo_upload);
  set('btn-submit', T.btn_submit);
  set('btn-edit', T.btn_edit);
  set('hinweis-text', T.hinweis);

  if (document.title) document.title = T.page_title;
}

document.addEventListener('DOMContentLoaded', applyAntragTrans);
</script>
</body>
</html>
