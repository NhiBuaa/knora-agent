import React, { type AriaAttributes, type ReactElement } from "react";
import "../../styles/controls.css";

type ControlProps = {
  id?: string;
  className?: string;
  "aria-describedby"?: string;
  "aria-invalid"?: AriaAttributes["aria-invalid"];
};

export type FieldProps = {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  children: ReactElement<ControlProps>;
};

export function Field({ id, label, hint, error, children }: FieldProps) {
  if (typeof children.type !== "string" || !["input", "select", "textarea"].includes(children.type)) {
    throw new Error("Field requires one native input, select, or textarea child");
  }

  const describedBy = [children.props["aria-describedby"], hint && `${id}-hint`, error && `${id}-error`]
    .filter(Boolean).join(" ") || undefined;
  const control = React.cloneElement(children, {
    id,
    className: ["kn-field__control", children.props.className].filter(Boolean).join(" "),
    "aria-describedby": describedBy,
    "aria-invalid": error ? true : children.props["aria-invalid"],
  });

  return <div className="kn-field">
    <label className="kn-field__label" htmlFor={id}>{label}</label>
    {control}
    {hint && <p className="kn-field__hint" id={`${id}-hint`}>{hint}</p>}
    {error && <p className="kn-field__error" id={`${id}-error`}>{error}</p>}
  </div>;
}
