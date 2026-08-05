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
  hintNode.hidden = true;

  const element = el('div', { class: 'stat-row' }, [
    el('span', { class: 'stat-label', text: label }),
    el('span', { class: 'stat-value-wrap' }, [valueNode, hintNode]),
  ]);

  return {
    element,
    /** Set the value, or pass null/undefined to show the empty text. */
    set(value, { hint = null } = {}) {
      const missing = value === null || value === undefined || value === '';
      valueNode.textContent = missing ? empty : `${value}${unit}`;
      valueNode.classList.toggle('is-empty', missing);
      hintNode.textContent = hint || '';
      hintNode.hidden = !hint;
    },
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
  element.hidden = true;

  return {
    element,
    /** Show this text, or hide the line entirely when text is falsy. */
    set(text, { icon: newIcon = null, tone = 'info' } = {}) {
      textNode.textContent = text || '';
      if (newIcon) {
        iconNode.setAttribute('icon', newIcon);
      }
      element.dataset.tone = tone;
      element.hidden = !text;
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

/**
 * A tab that is announced but not built yet.
 *
 * Used by the tabs that phase 7b and phase 8 fill in. It states plainly what
 * the tab will do and that it is not there yet, rather than showing an empty
 * page that reads as a broken panel. Delete this helper once every tab is real.
 */
export function placeholderTab({ id, label, icon, adminOnly, description }) {
  return {
    id,
    label,
    icon,
    adminOnly,
    create() {
      const { element, body } = card(label);
      body.append(
        el('p', { class: 'placeholder-text', text: description }),
        el('p', {
          class: 'placeholder-text',
          text: 'Dit tabblad wordt in een volgende versie toegevoegd.',
        }),
      );
      return {
        element: el('div', { class: 'tab-content' }, [element]),
        update() {},
      };
    },
  };
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
