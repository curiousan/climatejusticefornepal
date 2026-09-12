const icon = name => {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.classList.add('icon');
  svg.setAttribute('aria-hidden', 'true');
  const use = document.createElementNS(svg.namespaceURI, 'use');
  use.setAttribute('href', `#${name}`);
  svg.append(use);
  return svg;
};

function sourceUrl(value) {
  try {
    const url = new URL(value);
    return ['https:', 'http:'].includes(url.protocol) ? url.href : '';
  } catch { return ''; }
}

function imageUrl(value, imageBaseUrl) {
  if (typeof value !== 'string' || !value.trim()) return '';
  try {
    const base = /^(?:assets\/)?images\/carousel\//.test(value) ? document.baseURI : imageBaseUrl;
    const url = new URL(value, base);
    return url.protocol === 'https:' || (url.origin === location.origin && url.protocol === location.protocol) ? url.href : '';
  } catch { return ''; }
}

export function initCarousel({ openDialog, config = {} }) {
  const section = document.querySelector('#stories');
  const gallery = section.querySelector('#gallery');
  const previous = section.querySelector('#gallery-prev');
  const next = section.querySelector('#gallery-next');
  const toggle = section.querySelector('#gallery-toggle');
  const count = section.querySelector('#gallery-count');
  const dots = section.querySelector('#gallery-dots');
  const progress = section.querySelector('#gallery-progress-bar');
  const announcement = section.querySelector('#gallery-announcement');
  const lightbox = document.querySelector('#lightbox');
  const lightboxImage = lightbox.querySelector('#lightbox-image');
  const lightboxCaption = lightbox.querySelector('#lightbox-caption');
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  const manifestUrl = new URL(config.dataUrl || 'data/emission-contribution.json', document.baseURI);
  const imageBaseUrl = new URL(config.imageBaseUrl || 'assets/images/carousel/', document.baseURI);
  const interval = Number.isFinite(config.intervalMs) && config.intervalMs > 0 ? config.intervalMs : 7000;

  let cards = [...gallery.querySelectorAll('.gallery-card')];
  let slides = cards.map(card => ({
    overlay_text: card.querySelector('h3')?.textContent || '',
    source: card.querySelector('.gallery-source')?.textContent.trim() || '',
    'source link': card.querySelector('.gallery-source')?.href || '',
    image: card.querySelector('img').src,
    image_caption: card.querySelector('.image-caption')?.textContent || '',
  }));
  let active = 0;
  let lightboxIndex = 0;
  let userPaused = motion.matches;
  let inView = false;
  let hovering = false;
  let focusPaused = false;
  let timer;
  let scrollFrame;
  let pendingTarget = null;

  const modulo = index => (index % slides.length + slides.length) % slides.length;
  const canRotate = () => slides.length > 1 && !userPaused && inView && !hovering &&
    !focusPaused && !document.hidden && !document.querySelector('dialog[open]');

  function schedule() {
    clearTimeout(timer);
    gallery.setAttribute('aria-live', canRotate() ? 'off' : 'polite');
    toggle.disabled = slides.length < 2;
    toggle.setAttribute('aria-label', userPaused ? 'Play slideshow' : 'Pause slideshow');
    toggle.setAttribute('aria-pressed', String(!userPaused));
    toggle.title = userPaused ? 'Play slideshow' : 'Pause slideshow';
    const glyph = userPaused ? '▶' : 'Ⅱ';
    const toggleIcon = toggle.querySelector('span');
    // Preserve the click target when focus changes between pointerdown and up.
    if (toggleIcon.textContent !== glyph) toggleIcon.textContent = glyph;
    if (canRotate() && pendingTarget === null) timer = setTimeout(() => goTo(active + 1, false), interval);
  }

  function update(manual = false) {
    gallery.dataset.activeIndex = String(active);
    count.textContent = `${String(active + 1).padStart(2, '0')} / ${String(slides.length).padStart(2, '0')}`;
    progress.style.width = `${100 / slides.length}%`;
    progress.style.transform = `translateX(${active * 100}%)`;
    previous.disabled = next.disabled = slides.length < 2;
    cards.forEach((card, index) => {
      const current = index === active;
      card.classList.toggle('is-active', current);
      card.inert = !current;
      card.setAttribute('aria-hidden', String(!current));
      card.setAttribute('aria-label', `${index + 1} of ${slides.length}`);
      dots.children[index]?.setAttribute('aria-current', String(current));
    });
    // Load the next photograph before it is needed, without downloading the whole list.
    cards[modulo(active + 1)]?.querySelector('img').setAttribute('loading', 'eager');
    if (manual) announcement.textContent = `Photograph ${active + 1} of ${slides.length}. ${slides[active].overlay_text}`;
  }

  function goTo(index, manual = true) {
    if (!slides.length) return;
    const target = modulo(index);
    const wraps = Math.abs(target - active) > 1;
    const left = cards[target].offsetLeft - cards[0].offsetLeft;
    pendingTarget = Math.abs(gallery.scrollLeft - left) > 2 ? target : null;
    active = target;
    update(manual);
    gallery.scrollTo({
      left,
      behavior: motion.matches || wraps ? 'instant' : 'smooth',
    });
    // Instant moves complete synchronously, before their queued scroll event.
    if (Math.abs(gallery.scrollLeft - left) <= 2) pendingTarget = null;
    schedule();
  }

  function syncScroll() {
    if (!cards.length) return;
    // Keep a requested slide selected while the browser animates toward it.
    // Otherwise intermediate scroll events can reverse a rapid second click.
    if (pendingTarget !== null) {
      const destination = cards[pendingTarget].offsetLeft - cards[0].offsetLeft;
      if (Math.abs(gallery.scrollLeft - destination) > 2) return;
      pendingTarget = null;
    }
    const position = gallery.scrollLeft + cards[0].offsetLeft;
    const nearest = cards.reduce((best, card, index) =>
      Math.abs(card.offsetLeft - position) < Math.abs(cards[best].offsetLeft - position) ? index : best, 0);
    if (nearest !== active) {
      active = nearest;
      update();
    }
    schedule();
  }

  function prepareImage(card) {
    const photo = card.querySelector('img');
    const fail = () => {
      photo.hidden = true;
      card.querySelector('.gallery-image').classList.add('image-unavailable');
      card.querySelector('.image-fallback-message').hidden = false;
      card.querySelector('[data-slide]').disabled = true;
    };
    photo.addEventListener('error', fail, { once: true });
    if (photo.complete && !photo.naturalWidth) fail();
  }

  function setupCards() {
    cards = [...gallery.querySelectorAll('.gallery-card')];
    dots.replaceChildren();
    cards.forEach((card, index) => {
      card.setAttribute('role', 'group');
      card.setAttribute('aria-roledescription', 'slide');
      prepareImage(card);
      const dot = document.createElement('button');
      dot.type = 'button';
      dot.className = 'carousel-dot';
      dot.setAttribute('aria-label', `Go to photograph ${index + 1}`);
      dot.addEventListener('click', () => goTo(index));
      dots.append(dot);
    });
    dots.hidden = slides.length < 2 || slides.length > 8;
    active = Math.min(active, slides.length - 1);
    update();
    schedule();
  }

  function renderSlide(slide, index) {
    const card = document.createElement('figure');
    card.className = 'gallery-card';
    const stage = document.createElement('div');
    stage.className = 'gallery-image';
    const photo = document.createElement('img');
    photo.src = slide.image;
    photo.alt = slide.image_caption || 'Carousel photograph';
    photo.width = 1600;
    photo.height = 900;
    photo.loading = 'lazy';
    photo.decoding = 'async';
    const overlay = document.createElement('div');
    overlay.className = 'gallery-overlay';
    const heading = document.createElement('h3');
    heading.textContent = slide.overlay_text;
    heading.hidden = !slide.overlay_text;
    const source = document.createElement(slide['source link'] ? 'a' : 'span');
    source.className = 'gallery-source';
    source.textContent = slide.source || (slide['source link'] ? 'View source' : '');
    source.hidden = !source.textContent;
    if (slide['source link']) {
      source.href = slide['source link'];
      source.target = '_blank';
      source.rel = 'noopener noreferrer';
      source.append(icon('arrow-up-right'));
    }
    overlay.append(heading, source);
    const expand = document.createElement('button');
    expand.type = 'button';
    expand.className = 'gallery-expand';
    expand.dataset.slide = String(index);
    expand.setAttribute('aria-label', `Enlarge photograph ${index + 1}`);
    expand.append(icon('arrow-up-right'));
    const fallback = document.createElement('span');
    fallback.className = 'image-fallback-message';
    fallback.textContent = 'Photograph unavailable';
    fallback.hidden = true;
    stage.append(photo, overlay, expand, fallback);
    const caption = document.createElement('figcaption');
    const credit = document.createElement('p');
    credit.className = 'image-caption';
    credit.textContent = slide.image_caption;
    caption.append(credit);
    card.append(stage, caption);
    return card;
  }

  async function loadSlides() {
    gallery.setAttribute('aria-busy', 'true');
    try {
      const response = await fetch(manifestUrl, { cache: 'no-cache', signal: AbortSignal.timeout(8000) });
      if (!response.ok) throw new Error('Carousel list unavailable');
      const text = await response.text();
      if (text.length > 1_000_000) throw new Error('Carousel list too large');
      const data = JSON.parse(text);
      const entries = Array.isArray(data) ? data : [data];
      const nextSlides = entries.slice(0, 100).filter(entry => entry && typeof entry === 'object')
        .map(entry => ({
          overlay_text: typeof entry.overlay_text === 'string' ? entry.overlay_text : '',
          source: typeof entry.source === 'string' ? entry.source : '',
          'source link': sourceUrl(entry['source link']),
          image: imageUrl(entry.image, imageBaseUrl),
          image_caption: typeof entry.image_caption === 'string' ? entry.image_caption : '',
        })).filter(entry => entry.image);
      if (!nextSlides.length) throw new Error('No usable carousel images');
      slides = nextSlides;
      active = 0;
      pendingTarget = null;
      gallery.replaceChildren(...slides.map(renderSlide));
      gallery.scrollLeft = 0;
      setupCards();
    } catch {
      // Keep the credited HTML photographs when a list is missing or being edited.
    } finally {
      gallery.setAttribute('aria-busy', 'false');
      gallery.dataset.loaded = 'true';
    }
  }

  function showPhoto(index) {
    lightboxIndex = modulo(index);
    const slide = slides[lightboxIndex];
    lightboxImage.hidden = false;
    lightboxImage.src = slide.image;
    lightboxImage.alt = slide.image_caption || 'Carousel photograph';
    lightboxCaption.textContent = slide.image_caption;
    lightbox.querySelector('#lightbox-prev').disabled = lightbox.querySelector('#lightbox-next').disabled = slides.length < 2;
  }

  previous.addEventListener('click', () => goTo(active - 1));
  next.addEventListener('click', () => goTo(active + 1));
  toggle.addEventListener('click', () => {
    userPaused = !userPaused;
    if (!userPaused) focusPaused = false; // Explicit play may resume with this button focused.
    schedule();
  });
  gallery.addEventListener('keydown', event => {
    if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
      event.preventDefault();
      goTo(event.key === 'Home' ? 0 : event.key === 'End' ? slides.length - 1 : active + (event.key === 'ArrowRight' ? 1 : -1));
    }
  });
  gallery.addEventListener('scroll', () => {
    clearTimeout(timer);
    if (scrollFrame) return;
    scrollFrame = requestAnimationFrame(() => { scrollFrame = null; syncScroll(); });
  }, { passive: true });
  gallery.addEventListener('scrollend', syncScroll);
  const interruptScroll = () => { pendingTarget = null; clearTimeout(timer); };
  gallery.addEventListener('pointerdown', interruptScroll, { passive: true });
  gallery.addEventListener('wheel', interruptScroll, { passive: true });
  new ResizeObserver(() => {
    pendingTarget = null;
    gallery.scrollTo({ left: cards[active].offsetLeft - cards[0].offsetLeft, behavior: 'instant' });
    update();
    schedule();
  }).observe(gallery);
  new IntersectionObserver(([entry]) => { inView = entry.isIntersecting; schedule(); }, { threshold: 0.25 }).observe(gallery);
  gallery.addEventListener('pointerenter', event => { if (event.pointerType === 'mouse') { hovering = true; schedule(); } });
  gallery.addEventListener('pointerleave', () => { hovering = false; schedule(); });
  section.addEventListener('focusin', () => { focusPaused = true; schedule(); });
  section.addEventListener('focusout', () => queueMicrotask(() => {
    focusPaused = section.contains(document.activeElement);
    schedule();
  }));
  document.addEventListener('visibilitychange', schedule);
  document.addEventListener('close', schedule, true);
  motion.addEventListener('change', event => { if (event.matches) userPaused = true; schedule(); });
  gallery.addEventListener('click', event => {
    const button = event.target.closest('[data-slide]');
    if (!button || button.disabled) return;
    showPhoto(Number(button.dataset.slide));
    openDialog(lightbox);
    schedule();
  });
  lightbox.querySelector('#lightbox-prev').addEventListener('click', () => showPhoto(lightboxIndex - 1));
  lightbox.querySelector('#lightbox-next').addEventListener('click', () => showPhoto(lightboxIndex + 1));
  lightbox.addEventListener('keydown', event => {
    if (['ArrowLeft', 'ArrowRight'].includes(event.key)) {
      event.preventDefault();
      showPhoto(lightboxIndex + (event.key === 'ArrowRight' ? 1 : -1));
    }
  });
  lightboxImage.addEventListener('error', () => {
    lightboxImage.hidden = true;
    lightboxCaption.textContent = `Photograph unavailable. ${slides[lightboxIndex].image_caption}`;
  });

  setupCards();
  loadSlides();
}
