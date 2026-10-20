"use client";

import { useFormStatus } from "react-dom";

function Submit() {
  const { pending } = useFormStatus();
  return (
    <button type="submit" className="report-delete" disabled={pending}>
      {pending ? "삭제 중…" : "삭제"}
    </button>
  );
}

/** 처리를 마친 제보를 지운다. 되돌릴 수 없어서 한 번 묻는다. */
export default function DeleteButton({
  id,
  label,
  action,
}: {
  id: number;
  label: string;
  action: (formData: FormData) => Promise<void>;
}) {
  return (
    <form
      action={action}
      onSubmit={(e) => {
        if (!window.confirm(`${label} 제보를 삭제할까요? 되돌릴 수 없습니다.`)) e.preventDefault();
      }}
    >
      <input type="hidden" name="id" value={id} />
      <Submit />
    </form>
  );
}
