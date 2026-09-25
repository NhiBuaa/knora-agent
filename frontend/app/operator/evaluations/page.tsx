import { EvaluationView } from "../../../components/operator/EvaluationView";

export default function EvaluationsPage() {
  return (
    <>
      <h1>Evaluations</h1>
      <p>
        Evaluation reports are addressed by exact report ID. No client-side
        scoring is performed.
      </p>
      <EvaluationView
        evaluation={{
          availability: "unavailable",
          observation_failure: "REPORT_ID_REQUIRED",
          report_id: "not-selected",
          workspace_id: "",
        }}
      />
    </>
  );
}
