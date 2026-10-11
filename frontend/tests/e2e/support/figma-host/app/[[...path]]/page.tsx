import React, { Suspense } from "react";
import { FigmaFixtureView } from "../../../figma-fixture-view";

export default function FixturePage() {
  return (
    <Suspense>
      <FigmaFixtureView />
    </Suspense>
  );
}
