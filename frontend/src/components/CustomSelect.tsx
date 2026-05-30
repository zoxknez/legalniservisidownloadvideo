import { useState, useEffect, useRef, useLayoutEffect } from "react";
import type React from "react";
import { createPortal } from "react-dom";

export interface CustomSelectProps {
  value: string;
  options: string[];
  onChange: (val: string) => void;
  formatLabel?: (val: string) => string;
  className?: string;
  placeholder?: string;
  searchPlaceholder?: string;
}

export function CustomSelect({ value, options, onChange, formatLabel, className = "", placeholder, searchPlaceholder = "Pretraži..." }: CustomSelectProps) {
  const [open, setOpen] = useState(false);
  const [dropdownStyle, setDropdownStyle] = useState<React.CSSProperties | null>(null);
  const [filter, setFilter] = useState("");
  const triggerRef = useRef<HTMLButtonElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Recalculate position whenever dropdown opens
  useLayoutEffect(() => {
    if (open && triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      const spaceBelow = window.innerHeight - rect.bottom;
      const filteredCount = options.filter(opt =>
        (formatLabel ? formatLabel(opt) : opt).toLowerCase().includes(filter.toLowerCase())
      ).length;
      const hasSearch = options.length > 8;
      const searchHeight = hasSearch ? 45 : 0;
      const dropdownH = Math.min(filteredCount * 40 + searchHeight + 8, 280);
      const goUp = spaceBelow < dropdownH && rect.top > dropdownH;

      setDropdownStyle({
        position: "fixed",
        left: rect.left,
        right: "auto",
        width: rect.width,
        zIndex: 9999,
        ...(goUp
          ? { bottom: window.innerHeight - rect.top + 6 }
          : { top: rect.bottom + 6 }),
      });
    } else {
      setDropdownStyle(null);
    }
  }, [open, options, filter, formatLabel]);

  // Focus search input when dropdown opens
  useEffect(() => {
    if (open && searchInputRef.current) {
      const timer = setTimeout(() => {
        searchInputRef.current?.focus();
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [open]);

  // Reset filter when closed
  useEffect(() => {
    if (!open) {
      setFilter("");
    }
  }, [open]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      const t = e.target as Node;
      if (!triggerRef.current?.contains(t) && !dropdownRef.current?.contains(t)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  // Close on scroll / resize
  useEffect(() => {
    if (!open) return;
    const close = (e: Event) => {
      if (dropdownRef.current?.contains(e.target as Node)) {
        return;
      }
      setOpen(false);
    };
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    return () => {
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
    };
  }, [open]);

  const label = value
    ? (formatLabel ? formatLabel(value) : value)
    : (placeholder ?? "-- Izaberi --");

  const filteredOptions = options.filter(opt =>
    (formatLabel ? formatLabel(opt) : opt).toLowerCase().includes(filter.toLowerCase())
  );

  const dropdown = (open && dropdownStyle) ? createPortal(
    <div
      ref={dropdownRef}
      className="custom-select-dropdown"
      style={dropdownStyle}
    >
      {options.length > 8 && (
        <div className="custom-select-search-wrap">
          <input
            ref={searchInputRef}
            type="text"
            placeholder={searchPlaceholder}
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="custom-select-search-input"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
      {filteredOptions.length > 0 ? (
        filteredOptions.map(opt => (
          <button
            key={opt}
            type="button"
            onClick={() => { onChange(opt); setOpen(false); }}
            className={`custom-select-option ${value === opt ? "selected" : ""}`}
          >
            {formatLabel ? formatLabel(opt) : opt}
            {value === opt && (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{marginLeft: "auto", flexShrink: 0}}>
                <polyline points="20 6 9 17 4 12" />
              </svg>
            )}
          </button>
        ))
      ) : (
        <div style={{ padding: "12px 14px", color: "var(--text-muted)", fontSize: "0.8rem", textAlign: "center" }}>
          Nema rezultata
        </div>
      )}
    </div>,
    document.body
  ) : null;

  return (
    <div className={`custom-select-wrap ${className}`}>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen(o => !o)}
        className={`custom-select-trigger ${open ? "open" : ""}`}
      >
        <span className="custom-select-value">{label}</span>
        <svg className={`custom-select-chevron ${open ? "rotated" : ""}`} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      {dropdown}
    </div>
  );
}
