import { siteConfig } from './site.config.js';
import { initCarousel } from './carousel.js';

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');

// Navigation remains usable as ordinary anchor links without JavaScript.
const menuToggle = $('.menu-toggle');
const mobileNav = $('#mobile-nav');
function closeMenu() {
  mobileNav.hidden = true;
  menuToggle.setAttribute('aria-expanded', 'false');
  menuToggle.setAttribute('aria-label', 'Open navigation');
}
menuToggle.addEventListener('click', () => {
  const expanded = menuToggle.getAttribute('aria-expanded') !== 'true';
  menuToggle.setAttribute('aria-expanded', String(expanded));
  menuToggle.setAttribute('aria-label', expanded ? 'Close navigation' : 'Open navigation');
  mobileNav.hidden = !expanded;
});
$$('a', mobileNav).forEach(link => link.addEventListener('click', closeMenu));
document.addEventListener('keydown', event => { if (event.key === 'Escape') closeMenu(); });
matchMedia('(min-width: 1025px)').addEventListener('change', event => { if (event.matches) closeMenu(); });
const header = $('.site-header');
new ResizeObserver(() => {
  document.documentElement.style.setProperty('--header-height', `${header.offsetHeight}px`);
}).observe(header);

// Load the 2.3 MB silent derivative only when motion and data preferences allow it.
const video = $('#hero-video');
const videoToggle = $('#video-toggle');
let userPaused = false;
function syncVideoControl() {
  const playing = !video.paused;
  videoToggle.setAttribute('aria-label', `${playing ? 'Pause' : 'Play'} background video`);
  $('#video-toggle-icon').textContent = playing ? 'Ⅱ' : '▶';
}
async function playVideo() {
  if (!video.getAttribute('src')) video.src = video.dataset.src;
  try { await video.play(); } catch { /* The poster is the autoplay fallback. */ }
  syncVideoControl();
}
video.addEventListener('play', syncVideoControl);
video.addEventListener('pause', syncVideoControl);
videoToggle.addEventListener('click', () => {
  userPaused = !video.paused;
  if (userPaused) video.pause(); else playVideo();
});
const videoObserver = new IntersectionObserver(([entry]) => {
  if (!entry.isIntersecting) video.pause();
  else if (!userPaused && !reducedMotion.matches && !navigator.connection?.saveData) playVideo();
}, { threshold: 0.15 });
videoObserver.observe(video);
reducedMotion.addEventListener('change', event => { if (event.matches) video.pause(); });
document.addEventListener('visibilitychange', () => {
  if (document.hidden) video.pause();
  else if (!userPaused && !reducedMotion.matches && !navigator.connection?.saveData && video.getBoundingClientRect().bottom > 0) playVideo();
});

// Count up once on entry; source-backed final values remain available to readers.
// Leave time for the final browser paint before the one-second limit.
const COUNTER_DURATION_MS = 800;
const counterFrames = new WeakMap();
const counterDeadlines = new WeakMap();
const countedCounters = new WeakSet();
const counterLabels = new WeakMap();
const counterFormats = new Map();
function formatCounter(target, value, decimals = Number(target.dataset.decimals || 0)) {
  if (!counterFormats.has(decimals)) {
    counterFormats.set(decimals, new Intl.NumberFormat('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }));
  }
  const number = counterFormats.get(decimals).format(value);
  return `${target.dataset.prefix || ''}${number}${target.dataset.suffix || ''}`;
}
function fitHeroCounter(target) {
  const slot = target.closest('.hero-counter-value');
  if (!slot) return;
  target.style.removeProperty('transform');
  const width = target.getBoundingClientRect().width;
  if (!width) return;
  target.style.transformOrigin = 'left center';
  target.style.transform = `scaleX(${Math.min(1, slot.getBoundingClientRect().width / width)})`;
}
function clearCounterFit(target) {
  target.style.removeProperty('transform');
  target.style.removeProperty('transform-origin');
}
function cancelCounter(target) {
  cancelAnimationFrame(counterFrames.get(target));
  clearTimeout(counterDeadlines.get(target));
  counterFrames.delete(target);
  counterDeadlines.delete(target);
}
function finishCounter(target) {
  cancelCounter(target);
  target.textContent = formatCounter(target, Number(target.dataset.count));
  if (target.closest('.hero-counter-value')) clearCounterFit(target);
}
function animateCounters(targets, start) {
  targets.forEach(target => {
    if (countedCounters.has(target)) return;
    countedCounters.add(target);
    if (reducedMotion.matches || document.hidden || performance.now() - start >= COUNTER_DURATION_MS) {
      finishCounter(target);
      return;
    }
    const total = Number(target.dataset.count);
    const animationDecimals = target.dataset.animationDecimals;
    const granular = animationDecimals !== undefined;
    const decimals = granular ? Number(animationDecimals) : Number(target.dataset.decimals || 0);
    const precision = 10 ** decimals;
    const fitDuringAnimation = granular && target.closest('.hero-counter-value');
    target.textContent = formatCounter(target, 0, decimals);
    // Keep the sentence at its final width while an extra decimal counts up.
    if (fitDuringAnimation) fitHeroCounter(target);
    const tick = () => {
      if (!counterDeadlines.has(target)) return;
      const progress = Math.min((performance.now() - start) / COUNTER_DURATION_MS, 1);
      if (progress === 1) {
        finishCounter(target);
        return;
      }
      const eased = granular ? progress * progress * (3 - 2 * progress) : 1 - Math.pow(1 - progress, 3);
      // Additional decimal places make even 0.01 visibly count up. Truncation
      // keeps the final total for the end rather than rounding to it early.
      const value = granular
        ? Math.max(0, Math.min(Math.floor(total * eased * precision), Math.ceil(total * precision) - 1)) / precision
        : total * eased;
      target.textContent = formatCounter(target, value, decimals);
      if (fitDuringAnimation) fitHeroCounter(target);
      counterFrames.set(target, requestAnimationFrame(tick));
    };
    // Finish on elapsed time even when animation frames arrive late or stop.
    counterDeadlines.set(target, setTimeout(() => finishCounter(target),
      Math.max(0, start + COUNTER_DURATION_MS - performance.now())));
    counterFrames.set(target, requestAnimationFrame(tick));
    if (fitDuringAnimation && document.fonts?.status !== 'loaded') {
      document.fonts?.ready.then(() => {
        if (counterFrames.has(target) && !reducedMotion.matches) fitHeroCounter(target);
      });
    }
  });
}
const countObserver = new IntersectionObserver(entries => {
  entries.filter(entry => entry.isIntersecting).forEach(({ target, time }) => {
    countObserver.unobserve(target);
    animateCounters([target], time);
  });
}, { threshold: 0 });
const heroCounters = [];
$$('[data-count]').forEach(element => {
  // A stable text equivalent avoids announcing intermediate animation values.
  const namedElement = element.closest('.big-number') || element;
  const readable = document.createElement('span');
  readable.className = 'visually-hidden';
  readable.textContent = namedElement.getAttribute('aria-label') || element.textContent;
  element.before(readable);
  element.setAttribute('aria-hidden', 'true');
  namedElement.removeAttribute('aria-label');
  counterLabels.set(element, readable);
  if (element.closest('#hero-title')) heroCounters.push(element);
  else countObserver.observe(element);
});
if (heroCounters.length) {
  const heroCountObserver = new IntersectionObserver(entries => {
    const visible = entries.filter(entry => entry.isIntersecting);
    if (!visible.length) return;
    heroCountObserver.disconnect();
    animateCounters(heroCounters, Math.min(...visible.map(entry => entry.time)));
  }, { threshold: 0 });
  heroCountObserver.observe($('#hero-title'));
}
reducedMotion.addEventListener('change', event => {
  if (!event.matches) return;
  $$('[data-count]').forEach(finishCounter);
});
document.addEventListener('visibilitychange', () => {
  if (document.hidden) $$('[data-count]').filter(target => counterDeadlines.has(target)).forEach(finishCounter);
});

// Native dialogs provide keyboard focus management, Escape, and focus restoration.
function openDialog(dialog) {
  dialog.showModal();
  document.body.classList.add('modal-open');
}
$$('dialog').forEach(dialog => {
  $('[data-close]', dialog).addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => { if (event.target === dialog) {
    const rect = dialog.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
  }});
  dialog.addEventListener('close', () => document.body.classList.remove('modal-open'));
});
$('#sources-open').addEventListener('click', () => openDialog($('#sources-dialog')));
$('#footer-sources').addEventListener('click', () => openDialog($('#sources-dialog')));

initCarousel({ openDialog, config: siteConfig.carousel });

const shareText = $('.share-copy').textContent;
const shareUrl = siteConfig.publicUrl || location.href.split('#')[0];
$('#share-url').value = shareUrl;
$('#share-facebook').href = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(shareUrl)}`;
$('#share-linkedin').href = `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(shareUrl)}`;
$('#share-email').href = `mailto:?subject=${encodeURIComponent('Climate justice for Nepal')}&body=${encodeURIComponent(`${shareText}\n\n${shareUrl}`)}`;
$('#share-open').addEventListener('click', () => openDialog($('#share-dialog')));
async function copyText(value, success) {
  try {
    await navigator.clipboard.writeText(value);
    $('#share-status').textContent = success;
  } catch {
    $('#share-url').value = value;
    $('#share-url').focus();
    $('#share-url').select();
    $('#share-status').textContent = 'Text selected. Use your device’s copy command to copy it.';
  }
}
$('#copy-link').addEventListener('click', () => copyText(shareUrl, 'Link copied. Thank you for sharing Nepal’s story.'));
$('#copy-message').addEventListener('click', () => copyText(`${shareText}\n\n${shareUrl}`, 'Message copied. Ready to share wherever you connect.'));
if (navigator.share) {
  $('#native-share').hidden = false;
  $('#native-share').addEventListener('click', async () => {
    try { await navigator.share({ title: 'Climate Justice for Nepal', text: shareText, url: shareUrl }); }
    catch (error) { if (error.name !== 'AbortError') $('#share-status').textContent = 'Choose one of the sharing options above, or copy the link.'; }
  });
}
$$('[data-contact]').forEach(link => {
  const kind = link.dataset.contact;
  const value = siteConfig.contact[kind];
  if (!value) { link.setAttribute('aria-disabled', 'true'); return; }
  link.href = kind === 'email' ? `mailto:${value}` : value;
  link.setAttribute('aria-label', kind === 'email' ? 'Contact by email' : `Connect on ${kind}`);
  link.title = link.getAttribute('aria-label');
  if (kind !== 'email') { link.target = '_blank'; link.rel = 'noopener noreferrer'; }
});
if (Object.values(siteConfig.contact).some(Boolean)) $('.contact-placeholder').hidden = true;

// Cached snapshots keep the page useful offline. Fetch time never replaces report dates.
const CACHE_KEY = 'nepal-impact-v1';
const CACHE_TTL = 15 * 60 * 1000;
function validDate(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
}
function validImpact(data) {
  return data?.event === 'Nepal floods · 26 August 2026' && data?.metrics &&
    validDate(data.verifiedAt) && Object.keys(data.metrics).length === 4 && ['deaths', 'missing', 'homes', 'damage'].every(key => {
    const metric = data.metrics[key];
    return metric && typeof metric.value === 'number' && Number.isFinite(metric.value) && metric.value >= 0 &&
      typeof metric.display === 'string' && typeof metric.source === 'string' &&
      validDate(metric.asOf) && /^https:\/\//.test(metric.url);
  });
}
const formatDate = value => new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${value}T00:00:00Z`));
function renderImpact(data) {
  $('#data-status').textContent = `Last verified ${formatDate(data.verifiedAt)}. Reported figures may be revised; each links to its dated source.`;
  for (const [key, metric] of Object.entries(data.metrics)) {
    const value = $(`[data-metric="${key}"]`);
    const source = $(`[data-source="${key}"]`);
    if (!value || !source) continue;
    cancelCounter(value);
    value.dataset.count = String(key === 'damage' ? metric.value / 1_000_000_000 : metric.value);
    value.textContent = metric.display;
    if (counterLabels.has(value)) counterLabels.get(value).textContent = `${metric.display} ${metric.label}`;
    source.href = metric.url;
    source.firstChild.textContent = `${metric.source.startsWith('UN') ? 'UN' : 'AP'} · ${formatDate(metric.asOf)} `;
  }
  const dates = Object.values(data.metrics).map(metric => metric.asOf).sort();
  $('#report-date').textContent = dates[0] === dates.at(-1) ? formatDate(dates[0]) : `${formatDate(dates[0])} – ${formatDate(dates.at(-1))}`;
  $('#report-date').dateTime = dates.at(-1);
  const details = $('#source-details');
  details.replaceChildren();
  for (const metric of Object.values(data.metrics)) {
    const paragraph = document.createElement('p');
    const heading = document.createElement('strong');
    heading.textContent = `${metric.label} · ${metric.display} · ${formatDate(metric.asOf)}`;
    const link = document.createElement('a');
    link.href = metric.url; link.target = '_blank'; link.rel = 'noopener noreferrer';
    link.textContent = `${metric.source} ↗`;
    paragraph.append(heading, document.createElement('br'), document.createTextNode(`${metric.note || ''} `), link);
    details.append(paragraph);
  }
}
async function refreshImpact() {
  let cache;
  try { cache = JSON.parse(localStorage.getItem(CACHE_KEY)); } catch { /* Private storage may be unavailable. */ }
  if (validImpact(cache?.data)) {
    renderImpact(cache.data);
    if (Date.now() - cache.fetchedAt < CACHE_TTL) return;
  }
  try {
    const response = await fetch('data/impact.json', { cache: 'no-cache', signal: AbortSignal.timeout(8000) });
    if (!response.ok) throw new Error('Snapshot unavailable');
    const data = await response.json();
    if (!validImpact(data)) throw new Error('Invalid snapshot');
    renderImpact(data);
    try { localStorage.setItem(CACHE_KEY, JSON.stringify({ data, fetchedAt: Date.now() })); } catch { /* Storage is optional. */ }
  } catch {
    $('#data-status').textContent = 'Showing the last available dated report. Updates are temporarily unavailable.';
  }
}
refreshImpact();
setInterval(() => { if (!document.hidden) refreshImpact(); }, CACHE_TTL);
