-- 앱 '패턴 오류 제보' 저장 테이블. 사이트 API(web/app/api/report)가 쓰고
-- 주인 페이지(/reports)가 읽는다. 둘 다 서버에서 service_role 키로 접근한다.
--
-- Supabase 대시보드 → SQL Editor에서 한 번 실행한다.
-- 그다음 Vercel 환경변수에 SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY를 넣는다.

create table if not exists public.pattern_reports (
  id                bigint generated always as identity primary key,
  created_at        timestamptz not null default now(),
  code              text not null,
  name              text not null,
  type              text not null check (type in ('missed', 'wrong')),
  pattern           text not null,          -- pat_double_bottom 등 (_form 없이)
  forming           boolean,                -- 오류 제보: 형성 중 패턴이었나
  pattern_start     date,                   -- 오류 제보: 패턴 첫 꼭짓점
  pattern_end       date,                   -- 오류 제보: 패턴 마지막 꼭짓점
  pattern_completed date,                   -- 오류 제보: 완성(돌파)일
  period_from       date,                   -- 사용자가 고른 기간 (선택)
  period_to         date,
  note              text,
  data_date         date,                   -- 사용자가 본 데이터 기준일
  app_version       text,
  platform          text
);

create index if not exists pattern_reports_created_at
  on public.pattern_reports (created_at desc);

-- 정책을 하나도 두지 않는다 → anon 키로는 읽기·쓰기 모두 막힌다.
-- 서버의 service_role 키만 RLS를 건너뛰어 접근한다.
alter table public.pattern_reports enable row level security;
