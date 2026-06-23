// Scroll-Animationen
const observer = new IntersectionObserver((entries) => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      e.target.classList.add('visible');
    }
  });
}, { threshold: 0.1 });

document.querySelectorAll('.reveal').forEach(el => observer.observe(el));

// Spenden-Buttons
function selectAmount(btn, amount) {
  document.querySelectorAll('.amount-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
}

// Knotenanzahl simulieren (wird später durch echte API ersetzt)
function animateCounter() {
  const el = document.getElementById('node-count');
  let count = 0;
  const target = 1; // Startet bei 1 — du selbst
  const timer = setInterval(() => {
    count++;
    el.textContent = count;
    if (count >= target) clearInterval(timer);
  }, 80);
}

animateCounter();

// Anmeldung
function handleSignup(e) {
  e.preventDefault();
  const email = document.getElementById('signup-email').value;
  const btn = e.target.querySelector('button[type="submit"]');
  btn.textContent = '✓ Eingetragen — wir melden uns!';
  btn.style.background = 'var(--green-l)';
  btn.disabled = true;
  // Hier später: fetch('/api/signup', { method: 'POST', body: JSON.stringify({email}) })
}
