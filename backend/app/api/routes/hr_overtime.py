"""P0.1-09 overtime APIs."""
from datetime import date,datetime,timezone
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,Field
from sqlalchemy.orm import Session
from app import models
from app.api.deps import current_user,employee_scope_ids,require_permission
from app.db.session import get_db
from app.modules.core.audit import log_audit
from app.modules.hr.overtime import calculate_candidate
from app.api.routes.approvals import ApprovalRequest, Department
router=APIRouter(prefix="/hr/overtime",tags=["hr","overtime"])
class Calc(BaseModel):
 from_date:date
 to_date:date
 employee_ids:list[str]|None=None
class Review(BaseModel):
 decision:Literal["approve","reject","return"]
 reason:str=Field(min_length=3,max_length=1000)
def frozen(db,d):return db.query(models.HRPayrollRun).filter(models.HRPayrollRun.year==d.year,models.HRPayrollRun.month==d.month,models.HRPayrollRun.status.in_(["prepared","approved","finalized","locked"])).first() is not None
def out(r):return {k:getattr(r,k) for k in ["id","employee_id","work_date","revision","status","day_type","policy_id","policy_version","raw_candidate_minutes","rounded_candidate_minutes","calculation_snapshot","input_fingerprint","source_event_ids","summary_id","summary_revision","roster_entry_id","approval_request_id","requested_by","submitted_at","supervisor_username","supervisor_decision","supervisor_reason","supervisor_at","hr_verifier","hr_decision","hr_reason","hr_verified_at"]}
@router.post("/calculate")
def calculate(p:Calc,db:Session=Depends(get_db),u:models.User=Depends(require_permission("hr","overtime","calculate","tenant"))):
 if p.to_date<p.from_date or (p.to_date-p.from_date).days>92:raise HTTPException(422,"Invalid or too-long date range")
 q=db.query(models.Employee).filter(models.Employee.active.is_(True))
 if p.employee_ids is not None:q=q.filter(models.Employee.id.in_(p.employee_ids))
 results=[]
 for e in q.all():
  d=p.from_date
  while d<=p.to_date:
   if frozen(db,d):results.append({"employee_id":e.id,"work_date":d,"state":"blocked","reason":"payroll_frozen"});d=date.fromordinal(d.toordinal()+1);continue
   try:x=calculate_candidate(db,e.id,d,u.username)
   except ValueError as ex:x={"state":"blocked","reason":"policy_or_break_configuration","detail":str(ex)}
   if x.get("state")!="candidate":results.append({"employee_id":e.id,"work_date":d,**x});d=date.fromordinal(d.toordinal()+1);continue
   old=db.query(models.HROvertimeCandidate).filter_by(employee_id=e.id,work_date=d,input_fingerprint=x["input_fingerprint"]).first()
   if old:results.append({"candidate":out(old),"created":False});d=date.fromordinal(d.toordinal()+1);continue
   prev=db.query(models.HROvertimeCandidate).filter_by(employee_id=e.id,work_date=d).order_by(models.HROvertimeCandidate.revision.desc()).first()
   if prev and prev.status in {"submitted","supervisor_approved","approved"}:results.append({"state":"blocked","reason":"prior_candidate_in_review","employee_id":e.id,"work_date":d});d=date.fromordinal(d.toordinal()+1);continue
   snap={k:v for k,v in x.items() if k not in {"employee_id","work_date","calculated_by"}}
   row=models.HROvertimeCandidate(employee_id=e.id,work_date=d,revision=prev.revision+1 if prev else 1,supersedes_id=prev.id if prev else None,status="candidate",day_type=x["day_type"],policy_id=x["policy_id"],policy_version=x["policy_version"],raw_candidate_minutes=x["raw_candidate_minutes"],rounded_candidate_minutes=x["rounded_candidate_minutes"],calculation_snapshot=snap,input_fingerprint=x["input_fingerprint"],source_event_ids=x["source_event_ids"],summary_id=x["summary_id"],summary_revision=x["summary_revision"],roster_entry_id=x["roster_entry_id"])
   db.add(row);db.flush();log_audit(db,u.username,"CALCULATE","hr_overtime_candidate",row.id);results.append({"candidate":out(row),"created":True});d=date.fromordinal(d.toordinal()+1)
 db.commit();return {"processed":len(results),"results":results}
@router.get("")
def listing(from_date:date|None=None,to_date:date|None=None,employee_id:str|None=None,status:str|None=None,limit:int=Query(300,ge=1,le=1000),offset:int=0,db:Session=Depends(get_db),u:models.User=Depends(require_permission("hr","overtime","view","tenant"))):
 if from_date and to_date and to_date<from_date:raise HTTPException(422,"to_date cannot be earlier than from_date")
 if offset<0 or offset>1000000:raise HTTPException(422,"Overtime offset must be between 0 and 1000000")
 if from_date and to_date and (to_date-from_date).days+1>31:raise HTTPException(422,"Overtime query cannot exceed 31 calendar days")
 q=db.query(models.HROvertimeCandidate)
 if from_date:q=q.filter(models.HROvertimeCandidate.work_date>=from_date)
 if to_date:q=q.filter(models.HROvertimeCandidate.work_date<=to_date)
 if employee_id:q=q.filter(models.HROvertimeCandidate.employee_id==employee_id)
 if status:q=q.filter(models.HROvertimeCandidate.status==status)
 rows=q.order_by(models.HROvertimeCandidate.work_date.desc(),models.HROvertimeCandidate.id.desc()).all();scopes={}
 outrows=[]
 for r in rows:
  if r.work_date not in scopes:
   ids=employee_scope_ids(db,u,"hr","overtime","view",as_of_date=r.work_date);scopes[r.work_date]=None if ids is None else set(ids)
  if scopes[r.work_date] is None or r.employee_id in scopes[r.work_date]:outrows.append(out(r))
 return outrows[offset:offset+limit]
@router.get("/self")
def self_candidates(db:Session=Depends(get_db),u:models.User=Depends(current_user)):
 link=db.query(models.EmployeeUserLink).filter_by(user_id=u.id).first()
 if not link:raise HTTPException(403,"Login is not linked to employee")
 rows=db.query(models.HROvertimeCandidate).filter_by(employee_id=link.employee_id).order_by(models.HROvertimeCandidate.work_date.desc()).limit(200).all()
 return [out(x) for x in rows]
@router.get("/supervisor-queue")
def supervisor_queue(db:Session=Depends(get_db),u:models.User=Depends(current_user)):
 rows=db.query(models.HROvertimeCandidate).filter_by(supervisor_username=u.username,status="submitted").order_by(models.HROvertimeCandidate.work_date.desc()).limit(200).all()
 return [out(x) for x in rows]
@router.post("/{cid}/submit")
def submit(cid:str,db:Session=Depends(get_db),u:models.User=Depends(current_user)):
 r=db.get(models.HROvertimeCandidate,cid)
 if not r:raise HTTPException(404,"Candidate missing")
 if r.status not in {"candidate","returned"}:raise HTTPException(409,"Invalid state")
 if frozen(db,r.work_date):raise HTTPException(409,"Frozen payroll blocks submission")
 link=db.query(models.EmployeeUserLink).filter_by(user_id=u.id).first()
 if u.role not in (models.Role.admin,models.Role.hr) and (not link or link.employee_id!=r.employee_id):raise HTTPException(403,"Self-only submit")
 if r.requested_by and r.requested_by!=u.username:raise HTTPException(403,"Original requester only")
 emp=db.get(models.Employee,r.employee_id)
 assignment=db.query(models.EmployeeOrgAssignment).filter(models.EmployeeOrgAssignment.employee_id==emp.id,models.EmployeeOrgAssignment.valid_from<=r.work_date,(models.EmployeeOrgAssignment.valid_to.is_(None)|(models.EmployeeOrgAssignment.valid_to>=r.work_date))).order_by(models.EmployeeOrgAssignment.valid_from.desc()).first()
 dept_name=assignment.department if assignment and assignment.department else emp.department
 dept=db.query(Department).filter(Department.active.is_(True),Department.code==dept_name).first()
 if dept is None:dept=db.query(Department).filter(Department.active.is_(True),Department.name==dept_name).first()
 if dept is None:raise HTTPException(409,"Department Core Approval routing is not configured for this employee/date")
 if dept.hod_username==u.username:raise HTTPException(409,"Requester cannot be the department HOD approver")
 approval=ApprovalRequest(department_id=dept.id,request_type="HR Overtime",reference_id=r.id,reference_no=f"{emp.emp_code}-{r.work_date.isoformat()}",title=f"Overtime approval: {emp.emp_code} {r.work_date}",amount=0,requested_by=u.username,status="Pending",remarks=f"Candidate {r.id}; raw {r.raw_candidate_minutes} min; rounded {r.rounded_candidate_minutes} min")
 db.add(approval);db.flush()
 r.requested_by=u.username;r.supervisor_username=dept.hod_username;r.approval_request_id=approval.id;r.status="submitted";r.submitted_at=datetime.now(timezone.utc)
 log_audit(db,u.username,"SUBMIT","hr_overtime_candidate",f"{r.id}; Core Approval request={approval.id}; department={dept.code}")
 db.commit();db.refresh(r);return out(r)
def earn(db,r,actor):
 c=r.calculation_snapshot.get("compensation_snapshot") or {}
 if c.get("method") not in {"comp_leave","both"}:return
 ratio=c.get("credit_minutes_per_source_minute")
 if not isinstance(ratio,(int,float)) or ratio<=0:raise HTTPException(409,"Comp leave ratio not configured")
 if db.query(models.HRCompLeaveCredit).filter_by(source_candidate_id=r.id,entry_type="earned").first():return
 n=r.rounded_candidate_minutes*float(ratio)
 db.add(models.HRCompLeaveCredit(employee_id=r.employee_id,source_candidate_id=r.id,entry_type="earned",source_minutes=r.rounded_candidate_minutes,credit_minutes=n,conversion_ratio_snapshot=ratio,policy_id=r.policy_id,policy_snapshot=c,reason="Earned after final HR verification",created_by=actor))
 log_audit(db,actor,"CREDIT","hr_comp_leave_credit",r.id)
@router.post("/{cid}/review")
def review(cid:str,p:Review,db:Session=Depends(get_db),u:models.User=Depends(current_user)):
 r=db.get(models.HROvertimeCandidate,cid)
 if not r:raise HTTPException(404,"Candidate missing")
 if frozen(db,r.work_date):raise HTTPException(409,"Payroll frozen")
 if r.status=="submitted":
  approval=db.get(ApprovalRequest,r.approval_request_id) if r.approval_request_id else None
  if not approval:raise HTTPException(409,"Core Approval request is missing")
  if approval.status=="Pending":raise HTTPException(409,"Department HOD/Core Approval is still pending")
  if approval.status=="Rejected":
   r.status="rejected";r.supervisor_decision="reject";r.supervisor_reason=approval.remarks or "Rejected in Core Approvals";r.supervisor_at=approval.decided_at or datetime.now(timezone.utc)
   log_audit(db,u.username,"SYNC_REJECT","hr_overtime_candidate",r.id);db.commit();db.refresh(r);return out(r)
  if approval.status!="Approved":raise HTTPException(409,"Core Approval is not approved")
  r.status="supervisor_approved";r.supervisor_decision="approve";r.supervisor_reason=approval.remarks or "Department HOD approved";r.supervisor_at=approval.decided_at or datetime.now(timezone.utc)
  log_audit(db,u.username,"SYNC_APPROVAL","hr_overtime_candidate",f"{r.id}; approval={approval.id}; approver={approval.decided_by}")
  db.commit();db.refresh(r);return out(r)
 elif r.status=="supervisor_approved":
  if u.role not in (models.Role.admin,models.Role.hr) or u.username in {r.requested_by,r.supervisor_username}:raise HTTPException(403,"Distinct HR/Admin verifier required")
  r.status={"approve":"approved","reject":"rejected","return":"returned"}[p.decision];r.hr_decision="verify" if p.decision=="approve" else p.decision;r.hr_reason=p.reason;r.hr_verifier=u.username;r.hr_verified_at=datetime.now(timezone.utc)
 else:raise HTTPException(409,"Candidate not awaiting Core Approval/HR verification")
 log_audit(db,u.username,p.decision.upper(),"hr_overtime_candidate",r.id)
 if r.status=="approved":earn(db,r,u.username)
 db.commit();db.refresh(r);return out(r)
@router.get("/{cid}/history")
def history(cid:str,db:Session=Depends(get_db),u:models.User=Depends(require_permission("hr","overtime","view","tenant"))):
 r=db.get(models.HROvertimeCandidate,cid)
 if not r:raise HTTPException(404,"Candidate missing")
 revisions=[out(x) for x in db.query(models.HROvertimeCandidate).filter_by(employee_id=r.employee_id,work_date=r.work_date).order_by(models.HROvertimeCandidate.revision).all()]
 audits=db.query(models.AuditLog).filter(models.AuditLog.entity=="hr_overtime_candidate",models.AuditLog.detail.contains(r.id)).order_by(models.AuditLog.at.asc()).all()
 return {"revisions":revisions,"audit_history":[{"at":x.at,"actor":x.username,"action":x.action,"detail":x.detail} for x in audits]}
@router.get("/compensatory-leave/credits")
def credits(employee_id:str|None=None,limit:int=Query(300,ge=1,le=1000),db:Session=Depends(get_db),u:models.User=Depends(require_permission("hr","comp_leave_credits","view","tenant"))):
 q=db.query(models.HRCompLeaveCredit)
 if employee_id:q=q.filter(models.HRCompLeaveCredit.employee_id==employee_id)
 return [{"id":x.id,"employee_id":x.employee_id,"candidate_id":x.source_candidate_id,"entry_type":x.entry_type,"source_minutes":x.source_minutes,"credit_minutes":float(x.credit_minutes),"ratio":float(x.conversion_ratio_snapshot),"policy_id":x.policy_id,"policy_snapshot":x.policy_snapshot,"reason":x.reason,"created_by":x.created_by,"created_at":x.created_at} for x in q.order_by(models.HRCompLeaveCredit.created_at.desc()).limit(limit).all()]
@router.post("/compensatory-leave/credits/{credit_id}/reverse")
def reverse(credit_id:str,reason:str=Query(min_length=3,max_length=1000),db:Session=Depends(get_db),u:models.User=Depends(require_permission("hr","comp_leave_credits","reverse","tenant"))):
 x=db.get(models.HRCompLeaveCredit,credit_id)
 if not x:raise HTTPException(404,"Credit missing")
 if x.entry_type!="earned":raise HTTPException(409,"Only earned credit may reverse")
 if db.query(models.HRCompLeaveCredit).filter_by(source_candidate_id=x.source_candidate_id,entry_type="reversal").first():raise HTTPException(409,"Already reversed")
 c=db.get(models.HROvertimeCandidate,x.source_candidate_id)
 if c and frozen(db,c.work_date):raise HTTPException(409,"Payroll frozen")
 rev=models.HRCompLeaveCredit(employee_id=x.employee_id,source_candidate_id=x.source_candidate_id,entry_type="reversal",source_minutes=x.source_minutes,credit_minutes=-float(x.credit_minutes),conversion_ratio_snapshot=x.conversion_ratio_snapshot,policy_id=x.policy_id,policy_snapshot=x.policy_snapshot,reason=reason,created_by=u.username)
 db.add(rev);log_audit(db,u.username,"REVERSE","hr_comp_leave_credit",x.id);db.commit();db.refresh(rev);return {"id":rev.id,"reversed_credit_id":x.id,"credit_minutes":float(rev.credit_minutes)}
