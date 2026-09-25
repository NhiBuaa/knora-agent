import React, { type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import "../../styles/controls.css";

type FieldBase = {
  id: string;
  label: string;
  helperText?: string;
  error?: string;
};

export type FieldProps =
  | (FieldBase & { as?: "input" } & Omit<InputHTMLAttributes<HTMLInputElement>, "id">)
  | (FieldBase & { as: "select" } & Omit<SelectHTMLAttributes<HTMLSelectElement>, "id">)
  | (FieldBase & { as: "textarea" } & Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "id">);

function FieldFrame({ id, label, helperText, error, control }: FieldBase & { control: ReactNode }) {
  return <div className="kn-field">
    <label className="kn-field__label" htmlFor={id}>{label}</label>
    {control}
    {helperText && <p className="kn-field__help" id={`${id}-helper`}>{helperText}</p>}
    {error && <p className="kn-field__error" id={`${id}-error`}>{error}</p>}
  </div>;
}

function describedBy(id: string, helperText?: string, error?: string, existing?: string) {
  return [existing, helperText && `${id}-helper`, error && `${id}-error`].filter(Boolean).join(" ") || undefined;
}

export function Field(props: FieldProps) {
  if (props.as === "select") {
    const { as: _as, id, label, helperText, error, className = "", ...nativeProps } = props;
    return <FieldFrame id={id} label={label} helperText={helperText} error={error} control={
      <select {...nativeProps} id={id} className={`kn-field__control ${className}`.trim()}
        aria-invalid={error ? true : nativeProps["aria-invalid"]}
        aria-describedby={describedBy(id, helperText, error, nativeProps["aria-describedby"])} />
    } />;
  }
  if (props.as === "textarea") {
    const { as: _as, id, label, helperText, error, className = "", ...nativeProps } = props;
    return <FieldFrame id={id} label={label} helperText={helperText} error={error} control={
      <textarea {...nativeProps} id={id} className={`kn-field__control ${className}`.trim()}
        aria-invalid={error ? true : nativeProps["aria-invalid"]}
        aria-describedby={describedBy(id, helperText, error, nativeProps["aria-describedby"])} />
    } />;
  }
  const { as: _as, id, label, helperText, error, className = "", ...nativeProps } = props;
  return <FieldFrame id={id} label={label} helperText={helperText} error={error} control={
    <input {...nativeProps} id={id} className={`kn-field__control ${className}`.trim()}
      aria-invalid={error ? true : nativeProps["aria-invalid"]}
      aria-describedby={describedBy(id, helperText, error, nativeProps["aria-describedby"])} />
  } />;
}
