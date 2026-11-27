"""Tenant-configurable P0.1-09 OT calculation and provenance."""
from datetime import date,timezone
import hashlib,json
from decimal import Decimal,ROUND_DOWN,ROUND_UP,ROUND_HALF_UP
from app import models

def scope_matches(scope,emp,org,roster,day):
 values={"branch_ids":org.branch_id if org else None,"departments":org.department if org else emp.department,"employee_types":emp.employee_type,"shift_ids":roster.shift_type_id if roster else None,"day_types":day}
 return all(not scope.get(k) or values[k] in scope[k] for k in values)
def resolve_policy(db,e,d,roster,day):
 rows=db.query(models.HROvertimePolicyVersion).filter(models.HROvertimePolicyVersion.status=="published",models.HROvertimePolicyVersion.effective_from<=d,(models.HROvertimePolicyVersion.effective_to.is_(None)|(models.HROvertimePolicyVersion.effective_to>=d)).all()
 org=db.query(models.EmployeeOrgAssignment).filter(models.EmployeeOrgAssignment.employee_id==e.id,models.EmployeeOrgAssignment.valid_from<=d,(models.EmployeeOrgAssignment.valid_to.is_(None)|(models.EmployeeOrgAssignment.valid_to>=d)).order_by(models.EmployeeOrgAssignment.valid_from.desc()).first()
 values={"branch_ids":org.branch_id if org else None,"departments":org.department if org else e.department,"employee_types":e.employee_type,"shift_ids":roster.shift_type_id if roster else None,"day_types":day}
 matches=[p for p in rows if scope_matches(p.scope or {},emp,org,roster,day)]
 if not matches:return None,org,"not_configured"
 spec=lambda p:sum(bool((p.scope or {}).get(k)) for k in values)
 n=max(spec(p) for p in matches);best=[p for p in matches if spec(p)==n]
 return (best[0],org,"configured") if len(best)==1 else (None,org,"ambiguous")
def round_minutes(raw,r):
 m=r.get("method");i=r.get("increment_minutes")
 if m=="none":return raw
 if not isinstance(i,int) or i<=0:raise ValueError("rounding increment required")
 q=Decimal(raw)/i
 mode={"floor":ROUND_DOWN,"ceil":ROUND_UP,"nearest":ROUND_HALF_UP}.get(m)
 if mode is None:raise ValueError("invalid rounding method")
 return int(q.to_integral_value(rounding=mode)*i)
def calculate_candidate(db,eid,d,actor):
 emp=db.get(models.Employee,eid)
 if not emp or not emp.active:return {"state":"blocked","reason":"employee missing/inactive"}
 roster=db.query(models.HRShiftRosterEntry).filter_by(employee_id=eid,work_date=d).first()
 day="weekly_off" if roster and roster.status=="weekly_off" else "holiday" if roster and roster.status=="holiday" else "scheduled_workday"
 if not roster:
  cal=db.query(models.HRCalendarDay).filter_by(work_date=d).first()
  if cal and cal.day_type=="holiday":day="holiday"
 pol,org,state=resolve_policy(db,emp,d,roster,day)
 if not pol:return {"state":"blocked","reason":state}
 c=pol.configuration or {};elig=c.get("eligibility") or {};rnd=c.get("rounding") or {};comp=c.get("compensation") or {}
 events=db.query(models.HRAttendanceEvent).filter_by(employee_id=eid,work_date=d).filter(models.HRAttendanceEvent.voided_at.is_(None)).order_by(models.HRAttendanceEvent.occurred_at_utc,models.HRAttendanceEvent.id).all()
 superseded={x[0] for x in db.query(models.HRAttendanceEvent.supersedes_event_id).filter(models.HRAttendanceEvent.supersedes_event_id.is_not(None)).all()};events=[x for x in events if x.id not in superseded]
 if not events:return {"state":"blocked","reason":"no attendance events"}
 work=[];breaks=[];start=None;bstart=None;bid=None;errors=[]
 for ev in events:
  t=ev.occurred_at_utc;t=t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t.astimezone(timezone.utc)
  if ev.event_type=="punch_in":
   if start:errors.append("duplicate_punch_in")
   else:start=t
  elif ev.event_type=="punch_out":
   if not start:errors.append("punch_out_without_punch_in")
   elif t<=start:errors.append("non_positive_interval")
   else:work.append((start,t))
   start=None
   if bstart:errors.append("break_not_closed");bstart=None;bid=None
  elif ev.event_type=="break_start":
   if bstart:errors.append("duplicate_break_start")
   elif not start:errors.append("break_without_work")
   else:bstart=t;bid=ev.break_rule_id
  elif ev.event_type=="break_end":
   if not bstart:errors.append("break_end_without_start")
   elif t<=bstart:errors.append("non_positive_break")
   else:breaks.append((bstart,t,bid))
   bstart=None;bid=None
 if start:errors.append("missing_punch_out")
 if bstart:errors.append("missing_break_end")
 if errors and elig.get("require_complete_attendance",True):return {"state":"blocked","reason":"attendance_exception","exception_codes":errors}
 def mins(iv):return sum(max(0,int((b-a).total_seconds()//60)) for a,b in iv)
 def breakmins(iv):
  total=0
  for a,b,rid in breaks:
   rule=db.get(models.HRShiftBreakRule,rid) if rid else None
   if not rule:return None
   if rule.is_paid:continue
   if iv is None:total+=int((b-a).total_seconds()//60)
   else:
    for x,y in iv:
     lo=max(a,x);hi=min(b,y)
     if hi>lo:total+=int((hi-lo).total_seconds()//60)
  return total
 actual=max(0,mins(work)-(breakmins(work) or 0));mode=c.get("workday_mode") if day=="scheduled_workday" else c.get(day+"_mode");raw=0
 if comp.get("method")=="disabled" or mode=="disabled":pass
 elif day!="scheduled_workday" and mode=="actual_work":raw=actual
 elif day=="scheduled_workday" and mode=="beyond_scheduled_net":
  if not roster or not roster.scheduled_start_at_utc or not roster.scheduled_end_at_utc:return {"state":"blocked","reason":"schedule_required"}
  scheduled=int((roster.scheduled_end_at_utc-roster.scheduled_start_at_utc).total_seconds()//60);unpaid=sum(int(x.get("planned_duration_minutes",0)) for x in (roster.break_rules_snapshot or []) if not x.get("is_paid",False));raw=max(0,actual-max(0,scheduled-unpaid))
 elif day=="scheduled_workday" and mode=="outside_scheduled_interval":
  if not roster or not roster.scheduled_start_at_utc or not roster.scheduled_end_at_utc:return {"state":"blocked","reason":"schedule_required"}
  eligible=[]
  if elig.get("pre_shift"):eligible += [(a,min(b,roster.scheduled_start_at_utc)) for a,b in work if a<roster.scheduled_start_at_utc and min(b,roster.scheduled_start_at_utc)>a]
  if elig.get("post_shift"):eligible += [(max(a,roster.scheduled_end_at_utc),b) for a,b in work if b>roster.scheduled_end_at_utc and b>max(a,roster.scheduled_end_at_utc)]
  raw=max(0,mins(eligible)-(breakmins(eligible) or 0))
 else:return {"state":"blocked","reason":"invalid_policy_mode"}
 if raw<int(elig.get("minimum_minutes",0)):raw=0
 cap=elig.get("maximum_minutes_per_day")
 if cap is not None:raw=min(raw,int(cap))
 rounded=round_minutes(raw,rnd)
 if rounded<=0:return {"state":"no_overtime","raw_candidate_minutes":raw}
 summary=db.query(models.HRAttendanceDailySummary).filter_by(employee_id=eid,work_date=d).first()
 fp=hashlib.sha256(json.dumps({"events":[[x.id,x.event_type,x.occurred_at_utc.isoformat(),x.break_rule_id] for x in events],"roster":roster.id if roster else None,"summary":summary.current_revision if summary else None,"policy":pol.id,"raw":raw,"rounded":rounded},sort_keys=True).encode()).hexdigest()
 return {"state":"candidate","employee_id":eid,"work_date":d,"day_type":day,"policy_id":pol.id,"policy_version":pol.version_code,"policy_scope":pol.scope,"calculation_mode":mode,"raw_candidate_minutes":raw,"rounded_candidate_minutes":rounded,"rounding_snapshot":rnd,"exception_codes":errors,"source_event_ids":[x.id for x in events],"summary_id":summary.id if summary else None,"summary_revision":summary.current_revision if summary else None,"roster_entry_id":roster.id if roster else None,"roster_version":roster.version if roster else None,"employee_branch_id":org.branch_id if org else None,"employee_department":org.department if org else emp.department,"employee_type":emp.employee_type,"shift_type_id":roster.shift_type_id if roster else None,"compensation_snapshot":comp,"input_fingerprint":fp,"calculated_by":actor}
