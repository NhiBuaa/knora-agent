import React, { type ButtonHTMLAttributes } from "react";
import "../../styles/controls.css";

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "quiet";
};

export function Button({ variant = "primary", type = "button", className = "", ...props }: ButtonProps) {
  return <button type={type} data-variant={variant} className={`kn-button ${className}`.trim()} {...props} />;
}
