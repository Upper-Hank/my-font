import { useEffect, useId, useRef, useState } from 'react';
import ChevronDownIcon from '@uplus-icon/react/icons/chevron-down';
import ChevronUpIcon from '@uplus-icon/react/icons/chevron-up';
import { iconProps } from './ui.jsx';

export default function SelectMenu({ ariaLabel, disabled, id, onChange, options, placeholder, value }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const triggerRef = useRef(null);
  const listboxId = useId();
  const selectedIndex = Math.max(0, options.findIndex((option) => option.value === value));
  const selected = options[selectedIndex];

  useEffect(() => {
    if (!open) return;
    if (disabled) { setOpen(false); return; }
    const closeOnOutside = (event) => {
      if (!rootRef.current?.contains(event.target)) setOpen(false);
    };
    const closeOnEscape = (event) => {
      if (event.key !== 'Escape') return;
      setOpen(false);
      triggerRef.current?.focus();
    };
    const frame = window.requestAnimationFrame(() => {
      rootRef.current?.querySelectorAll('[role="option"]')[selectedIndex]?.focus();
    });
    document.addEventListener('pointerdown', closeOnOutside);
    window.addEventListener('keydown', closeOnEscape);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener('pointerdown', closeOnOutside);
      window.removeEventListener('keydown', closeOnEscape);
    };
  }, [open, selectedIndex, disabled]);

  const focusOption = (index) => {
    const items = rootRef.current?.querySelectorAll('[role="option"]');
    if (!items?.length) return;
    items[(index + items.length) % items.length]?.focus();
  };

  const moveFocus = (event, index) => {
    if (event.key === 'Tab') {
      setOpen(false);
      triggerRef.current?.focus();
    } else if (event.key === 'ArrowDown') {
      event.preventDefault();
      focusOption(index + 1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      focusOption(index - 1);
    } else if (event.key === 'Home') {
      event.preventDefault();
      focusOption(0);
    } else if (event.key === 'End') {
      event.preventDefault();
      focusOption(options.length - 1);
    }
  };

  const select = (nextValue) => {
    onChange(nextValue);
    setOpen(false);
    triggerRef.current?.focus();
  };

  return (
    <div className="select-menu" ref={rootRef}>
      <button
        className="select-trigger"
        ref={triggerRef}
        type="button"
        id={id}
        disabled={disabled || !options.length}
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listboxId}
        onClick={() => setOpen((current) => !current)}
        onKeyDown={(event) => {
          if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
          event.preventDefault();
          setOpen(true);
        }}
      >
        <span>{selected?.label || placeholder || '选择'}</span>
        {open
          ? <ChevronUpIcon {...iconProps} size={20} />
          : <ChevronDownIcon {...iconProps} size={20} />}
      </button>
      {open ? (
        <div className="select-popover" id={listboxId} role="listbox" aria-label={ariaLabel}>
          {options.map((option, index) => (
            <button
              className="select-option"
              type="button"
              role="option"
              tabIndex={option.value === value ? 0 : -1}
              aria-selected={option.value === value}
              onClick={() => select(option.value)}
              onKeyDown={(event) => moveFocus(event, index)}
              key={option.value === '' ? '__empty' : option.value}
            >
              <span>{option.label}</span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
