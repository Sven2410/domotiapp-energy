/**
 * Building the fixed DOM once, and updating only values afterwards
 * (SPEC.md §9).
 *
 * Every helper here returns the element **plus** the functions that change it.
 * That is the whole point: a tab holds on to those functions and calls them on
 * an update, so there is never a reason to re-create a node or to assign
 * `innerHTML` again. Re-rendering a whole tab on every `hass` update would
 * throw away focus, scroll position and any half-typed input.
 */

/**
 * The class that hides an element, and the only way this panel hides anything.
 *
 * The bare `hidden` attribute is not enough. `[hidden] { display: none }` lives
 * in the user-agent stylesheet, and in the cascade a normal author declaration
 * beats a normal user-agent one whatever its specificity — so any rule of ours
 * that sets `display` silently defeats it. That is not a theoretical risk: it
 * left every tab panel, every tab button, four notices and the status banner
 * permanently on screen in phase 7a.
 *
 * So visibility is *our* contract: a class we set, backed by an `!important`
 * rule we own. `hidden` is still set alongside it, because it is what removes
 * the element from the accessibility tree (SPEC.md §23).
 */
export const HIDDEN_CLASS = 'is-hidden';

/**
 * Show or hide an element.
 *
 * Use this everywhere, including on elements that have no `display` rule of
 * their own today. One added rule in the stylesheet would otherwise turn such
 * an element into a silent bug months later.
 */
export function setVisible(element, visible) {
  element.classList.toggle(HIDDEN_CLASS, !visible);
  element.hidden = !visible;
}

/** Create an element, set properties and append children in one call. */
export function el(tag, options = {}, children = []) {
  const node = document.createElement(tag);
  const { class: className, text, attrs, ...properties } = options;

  if (className) {
    node.className = className;
  }
  if (text !== undefined) {
    node.textContent = text;
  }
  for (const [name, value] of Object.entries(attrs || {})) {
    node.setAttribute(name, value);
  }
  Object.assign(node, properties);
  for (const child of children) {
    node.appendChild(child);
  }
  return node;
}

/**
 * A titled ha-card.
 *
 * No background, radius or shadow is set on the card anywhere in this panel:
 * the user's theme styles `ha-card` itself, and overriding it would fight that
 * theme (SPEC.md §10).
 */
export function card(title) {
  const body = el('div', { class: 'card-body' });
  const element = el('ha-card', {}, [
    el('h2', { class: 'card-title', text: title }),
    body,
  ]);
  return { element, body };
}

/**
 * One label/value row.
 *
 * `set(value, options)` is the only way its contents change. Passing `null`
 * shows the empty text rather than leaving the row blank, because a blank row
 * reads as a defect while "Nog niet ingesteld" reads as an instruction
 * (SPEC.md §8).
 */
export function statRow(label, { unit = '', empty = 'Niet beschikbaar' } = {}) {
  const valueNode = el('span', { class: 'stat-value', text: empty });
  const hintNode = el('span', { class: 'stat-hint' });
  setVisible(hintNode, false);

  const element = el('div', { class: 'stat-row' }, [
    el('span', { class: 'stat-label', text: label }),
    el('span', { class: 'stat-value-wrap' }, [valueNode, hintNode]),
  ]);

  return {
    element,
    /**
     * Set the value, or pass null/undefined to show the empty text.
     *
     * `empty` can be overridden per call, because one row can be blank for more
     * than one reason and "why" is the useful part: a price is absent on a
     * fixed contract for a different reason than when no price source can be
     * read, and telling the two apart is what saves a support call.
     */
    set(value, { hint = null, empty: emptyText = empty } = {}) {
      const missing = value === null || value === undefined || value === '';
      valueNode.textContent = missing ? emptyText : `${value}${unit}`;
      valueNode.classList.toggle('is-empty', missing);
      hintNode.textContent = hint || '';
      setVisible(hintNode, Boolean(hint));
    },
  };
}

/**
 * A headline figure: a small label above a large number.
 *
 * The hierarchy is the point. A score and its label at nearly the same weight
 * read as two equal facts; the number is the thing the customer came for, so
 * the label steps back into small letterspaced capitals and the figure
 * dominates.
 */
export function displayMetric(label, { suffix = '', empty = 'Nog niet berekend' } = {}) {
  const valueNode = el('span', { class: 'display-value', text: '—' });
  const suffixNode = el('span', { class: 'display-suffix', text: suffix });
  const emptyNode = el('span', { class: 'display-empty', text: empty });

  const element = el('div', { class: 'display-metric' }, [
    el('span', { class: 'label', text: label }),
    el('span', { class: 'display-figure' }, [valueNode, suffixNode, emptyNode]),
  ]);

  return {
    element,
    set(value) {
      const missing = value === null || value === undefined || value === '';
      valueNode.textContent = missing ? '' : String(value);
      setVisible(valueNode, !missing);
      setVisible(suffixNode, !missing && Boolean(suffix));
      setVisible(emptyNode, missing);
    },
  };
}

/**
 * One advice or warning, as a block rather than a bullet.
 *
 * A long sentence behind a bullet reads as an error list. A short marker above
 * the sentence, separated from its neighbours by a hairline, reads as advice —
 * which is what these are.
 */
export function adviceBlock() {
  const markerNode = el('span', { class: 'label' });
  const titleNode = el('p', { class: 'advice-item-title' });
  const messageNode = el('p', { class: 'advice-item-message' });
  const element = el('div', { class: 'advice-item' }, [
    markerNode,
    titleNode,
    messageNode,
  ]);

  return {
    element,
    set({ marker, title, message }) {
      markerNode.textContent = marker;
      titleNode.textContent = title;
      messageNode.textContent = message;
    },
  };
}

/**
 * A titled part of a dialog that can be folded away.
 *
 * A device has twenty-odd questions, and on a phone in a meter cupboard that is
 * one long scroll with no sense of where you are. Folding the parts nobody
 * needs on most visits — the control agreement, the optional entity links —
 * turns it into a short form with two things left to open.
 *
 * Built from a semantic `<button>` with `aria-expanded`, so a screen reader
 * announces the state and the keyboard opens it without anything of ours: the
 * chevron only repeats what the attribute already says (SPEC.md §23).
 */
let sectionCount = 0;

export function section(title, { open = true } = {}) {
  sectionCount += 1;
  const bodyId = `section-body-${sectionCount}`;

  const chevron = el('ha-icon', {
    class: 'section-chevron',
    attrs: { icon: 'mdi:chevron-down', 'aria-hidden': 'true' },
  });
  const toggle = el('button', {
    class: 'section-toggle',
    type: 'button',
    attrs: { 'aria-expanded': String(open), 'aria-controls': bodyId },
  });
  toggle.append(el('span', { class: 'section-title', text: title }), chevron);

  const body = el('div', { class: 'section-body', attrs: { id: bodyId } });
  const element = el('div', { class: 'section' }, [toggle, body]);

  function setOpen(next) {
    toggle.setAttribute('aria-expanded', String(next));
    chevron.setAttribute('icon', next ? 'mdi:chevron-down' : 'mdi:chevron-right');
    setVisible(body, next);
  }

  setOpen(open);
  toggle.addEventListener('click', () =>
    setOpen(toggle.getAttribute('aria-expanded') !== 'true'),
  );

  return {
    element,
    body,
    setOpen,
    isOpen: () => toggle.getAttribute('aria-expanded') === 'true',
  };
}

/**
 * A line of text that can be hidden, with an icon beside it.
 *
 * The icon is always accompanied by text: information is never carried by an
 * icon or a colour alone (SPEC.md §23).
 */
export function notice(icon) {
  const iconNode = el('ha-icon', { attrs: { icon, 'aria-hidden': 'true' } });
  const textNode = el('span', { class: 'notice-text' });
  const element = el('div', { class: 'notice' }, [iconNode, textNode]);
  setVisible(element, false);

  return {
    element,
    /**
     * Show this text, or hide the whole line when the text is falsy.
     *
     * The icon is hidden together with the text, never on its own: an icon
     * left behind without its sentence carries meaning by picture alone, which
     * SPEC.md §23 forbids.
     */
    set(text, { icon: newIcon = null, tone = 'info' } = {}) {
      textNode.textContent = text || '';
      if (newIcon) {
        iconNode.setAttribute('icon', newIcon);
      }
      element.dataset.tone = tone;
      setVisible(element, Boolean(text));
    },
  };
}

/** A semantic button. Keyboard operable for free, which §23 requires. */
export function button(label, { primary = false } = {}) {
  return el('button', {
    class: primary ? 'button button-primary' : 'button',
    type: 'button',
    text: label,
  });
}

/** Format a number the way the panel shows measurements. */
export function formatNumber(value, { decimals = 0 } = {}) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return null;
  }
  return new Intl.NumberFormat('nl-NL', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

/**
 * Format an amount in euros per kWh.
 *
 * Three decimals, because a tariff is quoted in tenths of a cent and two would
 * round two different prices onto the same figure.
 */
export function formatPrice(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return null;
  }
  return new Intl.NumberFormat('nl-NL', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 3,
    maximumFractionDigits: 3,
  }).format(value);
}

/**
 * Say when a moment is, the way somebody says it out loud.
 *
 * *"morgen om 07:00"* rather than *"12-08-2026, 07:00:00"*, because this lands
 * in a sentence a resident reads once and has to act on: he fills the
 * dishwasher at ten in the evening and needs to know the flag still counts
 * tomorrow morning (SPEC.md §32.6).
 *
 * Two horizons, which is all a shelf life of at most a day can produce: later
 * today, or tomorrow. Anything further is a moment this flag cannot reach, so
 * there is no branch for it.
 */
export function formatMoment(iso) {
  if (!iso) {
    return null;
  }
  const moment = new Date(iso);
  if (Number.isNaN(moment.getTime())) {
    return null;
  }
  const time = new Intl.DateTimeFormat('nl-NL', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(moment);

  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const days = Math.floor((moment - startOfToday) / 86400000);
  return days >= 1 ? `morgen om ${time}` : `vandaag om ${time}`;
}

/** Format an ISO timestamp as a readable Dutch date and time. */
export function formatTimestamp(iso) {
  if (!iso) {
    return null;
  }
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  return new Intl.DateTimeFormat('nl-NL', {
    dateStyle: 'short',
    timeStyle: 'medium',
  }).format(parsed);
}
