/** Presentation language only; this never changes the server's evidence decision. */
export function isVietnameseQuestion(question: string = ""): boolean {
  if (
    /[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]/i.test(
      question,
    )
  )
    return true;
  const words = question
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  // Match characteristic phrases, rather than ambiguous single words such as “do”.
  return /(?:^| )(?:alo|xin chao|ai do|bao nhieu|tai lieu|cau hoi|cho toi|ban co|la gi|nhu the nao|tom tat|so sanh|bang chung)(?: |$)/.test(
    words,
  );
}
