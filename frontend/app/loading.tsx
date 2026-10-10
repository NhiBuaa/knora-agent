import React from "react";
import { LeafLoading } from "@/components/ui/LeafLoading";
export default function Loading() {
  return (
    <div className="grid min-h-[40vh] place-items-center">
      <LeafLoading label="Loading Knora" />
    </div>
  );
}
