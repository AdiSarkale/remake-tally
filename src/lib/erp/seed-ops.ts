import type { OpsState } from "./ops-types";

/** Demo data for the operational modules. `iso(daysAgo)` matches the core seed clock. */
export function buildOpsSeed(iso: (daysAgo: number) => string): OpsState {
  const machines: OpsState["machines"] = [
    { id: "m1", code: "PRS-01", name: "Power Press 100T", department: "Press Shop", capacityPerHour: 420, status: "Running", installedOn: "2019-04-12" },
    { id: "m2", code: "PRS-02", name: "Power Press 60T", department: "Press Shop", capacityPerHour: 640, status: "Running", installedOn: "2020-08-03" },
    { id: "m3", code: "CNC-01", name: "CNC Turning Centre", department: "Machine Shop", capacityPerHour: 180, status: "Under Maintenance", installedOn: "2021-01-22" },
    { id: "m4", code: "THR-01", name: "Thread Rolling Machine", department: "Fasteners", capacityPerHour: 900, status: "Running", installedOn: "2018-11-05" },
    { id: "m5", code: "WLD-01", name: "MIG Welding Station", department: "Fabrication", capacityPerHour: 75, status: "Idle", installedOn: "2022-06-18" },
  ];

  const productionPlans: OpsState["productionPlans"] = [
    { id: "pp1", planNo: "PLN-2026-00001", date: iso(3), soNo: "SO-2026-00003", productName: "Sheet Metal Bracket A", plannedQty: 1200, producedQty: 1200, machineName: "Power Press 100T", shift: "A", startDate: iso(3), dueDate: iso(1), priority: "High", status: "Completed" },
    { id: "pp2", planNo: "PLN-2026-00002", date: iso(2), soNo: "SO-2026-00004", productName: "MS Hex Bolt M12", plannedQty: 8000, producedQty: 5200, machineName: "Thread Rolling Machine", shift: "B", startDate: iso(2), dueDate: iso(0), priority: "Urgent", status: "In Progress" },
    { id: "pp3", planNo: "PLN-2026-00003", date: iso(2), soNo: "SO-2026-00005", productName: "Sheet Metal Bracket B", plannedQty: 600, producedQty: 140, machineName: "Power Press 60T", shift: "A", startDate: iso(1), dueDate: iso(-2), priority: "Normal", status: "In Progress" },
    { id: "pp4", planNo: "PLN-2026-00004", date: iso(5), soNo: "SO-2026-00002", productName: "MS Hex Nut M12", plannedQty: 10000, producedQty: 4100, machineName: "CNC Turning Centre", shift: "C", startDate: iso(5), dueDate: iso(1), priority: "High", status: "Delayed" },
  ];

  const designRequests: OpsState["designRequests"] = [
    { id: "dr1", drNo: "DR-2026-00001", date: iso(12), customerName: "Tata Autocomp Systems", productName: "Bracket A — carton artwork", dieNo: "DIE-114", version: "v3", requirement: "4-colour print, revised logo placement", designer: "Anjali Rao", status: "Released", approvedBy: "Customer QA", approvedOn: iso(7) },
    { id: "dr2", drNo: "DR-2026-00002", date: iso(6), customerName: "Bharat Forge Ltd", productName: "Hex Bolt bulk pack label", dieNo: "DIE-121", version: "v2", requirement: "Add batch traceability QR block", designer: "Anjali Rao", status: "Sent to Customer", approvedBy: "", approvedOn: "" },
    { id: "dr3", drNo: "DR-2026-00003", date: iso(2), customerName: "Endurance Technologies", productName: "Bracket B blister layout", dieNo: "DIE-130", version: "v1", requirement: "New die, 6-cavity layout", designer: "Nikhil Deo", status: "Internal Review", approvedBy: "", approvedOn: "" },
  ];

  const inspections: OpsState["inspections"] = [
    { id: "qc1", qcNo: "QC-2026-00001", date: iso(4), stage: "Incoming", reference: "GRN-2026-00002", itemName: "MS Round Bar 12mm", inspectedQty: 500, acceptedQty: 492, rejectedQty: 8, inspector: "Prakash Jadhav", result: "Accepted with Deviation", remarks: "Minor surface pitting on 8 bars" },
    { id: "qc2", qcNo: "QC-2026-00002", date: iso(2), stage: "In-process", reference: "BATCH-0021", itemName: "Sheet Metal Bracket A", inspectedQty: 200, acceptedQty: 197, rejectedQty: 3, inspector: "Prakash Jadhav", result: "Accepted", remarks: "Burr on 3 pieces, reworked" },
    { id: "qc3", qcNo: "QC-2026-00003", date: iso(1), stage: "Final", reference: "DN-2026-00004", itemName: "MS Hex Bolt M12", inspectedQty: 1000, acceptedQty: 1000, rejectedQty: 0, inspector: "Sneha Kale", result: "Accepted", remarks: "Torque and thread gauge OK" },
    { id: "qc4", qcNo: "QC-2026-00004", date: iso(0), stage: "In-process", reference: "BATCH-0024", itemName: "Sheet Metal Bracket B", inspectedQty: 140, acceptedQty: 118, rejectedQty: 22, inspector: "Sneha Kale", result: "Rejected", remarks: "Bend angle out of tolerance — NCR raised" },
  ];

  const ncrs: OpsState["ncrs"] = [
    { id: "nc1", ncrNo: "NCR-2026-00001", date: iso(0), source: "In-process", description: "Bracket B bend angle 3° over tolerance on Press 60T", severity: "High", rootCause: "Die stopper wear", correction: "Segregated 22 pcs, re-bent", capaAction: "Replace stopper block; add die-wear check to shift checklist", owner: "Prakash Jadhav", dueDate: iso(-5), status: "CAPA Implemented" },
    { id: "nc2", ncrNo: "NCR-2026-00002", date: iso(9), source: "Customer", description: "Loose packing caused thread damage in transit", severity: "Medium", rootCause: "Insufficient partition in carton", correction: "Replacement lot dispatched", capaAction: "Revised carton design DR-2026-00001 released", owner: "Anjali Rao", dueDate: iso(2), status: "Closed" },
    { id: "nc3", ncrNo: "NCR-2026-00003", date: iso(4), source: "Incoming", description: "Surface pitting on MS round bar lot", severity: "Low", rootCause: "Supplier storage in open yard", correction: "8 bars returned", capaAction: "Supplier warned; covered storage clause added to PO terms", owner: "Meera Shah", dueDate: iso(-10), status: "Under Investigation" },
  ];

  const complaints: OpsState["complaints"] = [
    { id: "cp1", complaintNo: "CMP-2026-00001", date: iso(10), customerName: "Bharat Forge Ltd", invoiceNo: "SPW/26-27/0002", issue: "Thread damage on 40 bolts", severity: "Medium", assignedTo: "Sneha Kale", rootCause: "Packing partition missing", resolution: "Free replacement + carton redesign", status: "Closed", closedOn: iso(3) },
    { id: "cp2", complaintNo: "CMP-2026-00002", date: iso(2), customerName: "Endurance Technologies", invoiceNo: "SPW/26-27/0004", issue: "Short supply of 60 brackets", severity: "High", assignedTo: "Meera Shah", rootCause: "Picking error at FG store", resolution: "", status: "Investigating", closedOn: "" },
  ];

  const calibrations: OpsState["calibrations"] = [
    { id: "cal1", instrumentNo: "VC-01", instrument: "Vernier Caliper 0-150mm", location: "QC Lab", lastCalibrated: iso(120), nextDue: iso(-245), agency: "Precision Metrology Pune", certificateNo: "PMP/2026/0412" },
    { id: "cal2", instrumentNo: "MM-03", instrument: "Micrometer 0-25mm", location: "Machine Shop", lastCalibrated: iso(340), nextDue: iso(-25), agency: "Precision Metrology Pune", certificateNo: "PMP/2025/1188" },
    { id: "cal3", instrumentNo: "TQ-02", instrument: "Torque Wrench 20-100Nm", location: "Assembly", lastCalibrated: iso(360), nextDue: iso(-5), agency: "CalibTech Services", certificateNo: "CTS/2025/0771" },
  ];

  const maintenancePlans: OpsState["maintenancePlans"] = [
    { id: "mp1", machineName: "Power Press 100T", type: "Preventive", frequencyDays: 30, lastDone: iso(26), nextDue: iso(-4), technician: "Ganesh More", checklist: "Clutch, brake, lubrication, guard interlock" },
    { id: "mp2", machineName: "CNC Turning Centre", type: "AMC", frequencyDays: 90, lastDone: iso(88), nextDue: iso(-2), technician: "OEM Service", checklist: "Spindle alignment, coolant, ballscrew backlash" },
    { id: "mp3", machineName: "Thread Rolling Machine", type: "Lubrication", frequencyDays: 7, lastDone: iso(6), nextDue: iso(-1), technician: "Ganesh More", checklist: "Way oil, gearbox level" },
    { id: "mp4", machineName: "Power Press 60T", type: "Inspection", frequencyDays: 15, lastDone: iso(3), nextDue: iso(-12), technician: "Ganesh More", checklist: "Die stopper wear, ram parallelism" },
  ];

  const breakdowns: OpsState["breakdowns"] = [
    { id: "bd1", ticketNo: "BD-2026-00001", date: iso(5), machineName: "CNC Turning Centre", problem: "Spindle overheating alarm", downtimeMinutes: 320, technician: "OEM Service", sparesUsed: "Spindle bearing set", cost: 42000, status: "Resolved" },
    { id: "bd2", ticketNo: "BD-2026-00002", date: iso(1), machineName: "Power Press 60T", problem: "Ram creep on down stroke", downtimeMinutes: 95, technician: "Ganesh More", sparesUsed: "Brake lining", cost: 6200, status: "In Progress" },
    { id: "bd3", ticketNo: "BD-2026-00003", date: iso(0), machineName: "MIG Welding Station", problem: "Wire feeder jam", downtimeMinutes: 40, technician: "Ganesh More", sparesUsed: "Liner", cost: 900, status: "Open" },
  ];

  const spares: OpsState["spares"] = [
    { id: "sp1", code: "SPR-001", name: "Brake lining set", machineName: "Power Press 60T", stock: 2, minStock: 2, unitCost: 3100, location: "Maint. Store A1" },
    { id: "sp2", code: "SPR-002", name: "Spindle bearing", machineName: "CNC Turning Centre", stock: 1, minStock: 2, unitCost: 18500, location: "Maint. Store B2" },
    { id: "sp3", code: "SPR-003", name: "MIG torch liner", machineName: "MIG Welding Station", stock: 8, minStock: 4, unitCost: 450, location: "Maint. Store A3" },
    { id: "sp4", code: "SPR-004", name: "Die stopper block", machineName: "Power Press 60T", stock: 5, minStock: 3, unitCost: 2200, location: "Tool Room" },
  ];

  const dispatches: OpsState["dispatches"] = [
    { id: "ds1", dispatchNo: "DSP-2026-00001", date: iso(4), dnNo: "DN-2026-00001", customerName: "Tata Autocomp Systems", transporter: "VRL Logistics", vehicleNo: "MH12 AB 4412", driverName: "Rajesh Pawar", driverPhone: "9822011234", lrNumber: "VRL/PN/88213", podRef: "POD-88213.pdf", status: "Delivered", deliveredOn: iso(3) },
    { id: "ds2", dispatchNo: "DSP-2026-00002", date: iso(1), dnNo: "DN-2026-00003", customerName: "Bharat Forge Ltd", transporter: "TCI Freight", vehicleNo: "MH14 CD 9087", driverName: "Imran Shaikh", driverPhone: "9765443321", lrNumber: "TCI/PN/44190", podRef: "", status: "In Transit", deliveredOn: "" },
    { id: "ds3", dispatchNo: "DSP-2026-00003", date: iso(0), dnNo: "DN-2026-00004", customerName: "Endurance Technologies", transporter: "Own Vehicle", vehicleNo: "MH12 XY 1120", driverName: "Sachin Gaikwad", driverPhone: "9970012233", lrNumber: "", podRef: "", status: "Loading", deliveredOn: "" },
  ];

  const employees: OpsState["employees"] = [
    { id: "e1", empCode: "EMP-001", name: "Ravi Kulkarni", department: "Management", designation: "Managing Director", doj: "2012-04-01", mobile: "9822001122", monthlySalary: 250000, skillLevel: "Expert", status: "Active" },
    { id: "e2", empCode: "EMP-002", name: "Meera Shah", department: "Accounts", designation: "Accounts Manager", doj: "2016-07-11", mobile: "9822003344", monthlySalary: 85000, skillLevel: "Expert", status: "Active" },
    { id: "e3", empCode: "EMP-003", name: "Sunil Patil", department: "Production", designation: "Shift Supervisor", doj: "2018-02-19", mobile: "9822005566", monthlySalary: 42000, skillLevel: "Advanced", status: "Active" },
    { id: "e4", empCode: "EMP-004", name: "Prakash Jadhav", department: "Quality", designation: "QA Engineer", doj: "2019-09-02", mobile: "9822007788", monthlySalary: 48000, skillLevel: "Advanced", status: "Active" },
    { id: "e5", empCode: "EMP-005", name: "Ganesh More", department: "Maintenance", designation: "Maintenance Technician", doj: "2020-11-16", mobile: "9822009900", monthlySalary: 34000, skillLevel: "Intermediate", status: "Active" },
    { id: "e6", empCode: "EMP-006", name: "Anjali Rao", department: "Design", designation: "Design Engineer", doj: "2021-06-07", mobile: "9822011223", monthlySalary: 52000, skillLevel: "Advanced", status: "Active" },
    { id: "e7", empCode: "EMP-007", name: "Sneha Kale", department: "Quality", designation: "QC Inspector", doj: "2022-03-14", mobile: "9822013344", monthlySalary: 28000, skillLevel: "Intermediate", status: "Active" },
    { id: "e8", empCode: "EMP-008", name: "Nikhil Deo", department: "Design", designation: "Junior Designer", doj: "2024-01-08", mobile: "9822015566", monthlySalary: 24000, skillLevel: "Beginner", status: "Active" },
  ];

  const attendance: OpsState["attendance"] = [];
  const attStatus = ["Present", "Present", "Present", "Present", "Leave", "Absent", "Half Day"];
  employees.forEach((e, ei) => {
    for (let d = 0; d < 3; d++) {
      const status = attStatus[(ei + d * 2) % attStatus.length] as string;
      attendance.push({
        id: `att-${e.empCode}-${d}`,
        date: iso(d),
        empCode: e.empCode,
        empName: e.name,
        status,
        inTime: status === "Present" || status === "Half Day" ? "08:30" : "",
        outTime: status === "Present" ? "17:30" : status === "Half Day" ? "13:00" : "",
        overtimeHours: status === "Present" && ei % 3 === 0 ? 2 : 0,
      });
    }
  });

  const leaves: OpsState["leaves"] = [
    { id: "lv1", empCode: "EMP-007", empName: "Sneha Kale", type: "Casual", fromDate: iso(1), toDate: iso(0), days: 2, reason: "Family function", status: "Approved" },
    { id: "lv2", empCode: "EMP-005", empName: "Ganesh More", type: "Sick", fromDate: iso(-2), toDate: iso(-2), days: 1, reason: "Fever", status: "Pending" },
    { id: "lv3", empCode: "EMP-003", empName: "Sunil Patil", type: "Earned", fromDate: iso(-8), toDate: iso(-4), days: 5, reason: "Annual leave", status: "Pending" },
  ];

  const trainings: OpsState["trainings"] = [
    { id: "tr1", date: iso(20), empCode: "EMP-007", empName: "Sneha Kale", topic: "ISO 9001:2015 awareness", trainer: "External — QMS Consultants", hours: 8, effectiveness: "Effective" },
    { id: "tr2", date: iso(12), empCode: "EMP-003", empName: "Sunil Patil", topic: "Press shop safety & LOTO", trainer: "Internal — Plant Head", hours: 4, effectiveness: "Effective" },
    { id: "tr3", date: iso(4), empCode: "EMP-005", empName: "Ganesh More", topic: "Preventive maintenance planning", trainer: "OEM Service", hours: 6, effectiveness: "Retraining Needed" },
  ];

  const appraisals: OpsState["appraisals"] = [
    { id: "ap1", period: "FY 2025-26", empCode: "EMP-003", empName: "Sunil Patil", rating: 4.2, strengths: "Shift discipline, low rejection", improvement: "Documentation timeliness", incrementPercent: 9, status: "Approved" },
    { id: "ap2", period: "FY 2025-26", empCode: "EMP-004", empName: "Prakash Jadhav", rating: 4.6, strengths: "Strong root-cause analysis", improvement: "Delegation", incrementPercent: 11, status: "Reviewed" },
    { id: "ap3", period: "FY 2025-26", empCode: "EMP-008", empName: "Nikhil Deo", rating: 3.4, strengths: "Fast learner", improvement: "Die layout accuracy", incrementPercent: 6, status: "Draft" },
  ];

  const payments: OpsState["payments"] = [
    { id: "pay1", voucherNo: "RV-2026-00001", date: iso(6), direction: "Received", partyType: "Customer", party: "Tata Autocomp Systems", reference: "SPW/26-27/0001", mode: "RTGS", amount: 284500, remarks: "Full settlement" },
    { id: "pay2", voucherNo: "RV-2026-00002", date: iso(2), direction: "Received", partyType: "Customer", party: "Bharat Forge Ltd", reference: "SPW/26-27/0002", mode: "NEFT", amount: 120000, remarks: "Part payment" },
    { id: "pay3", voucherNo: "PV-2026-00001", date: iso(5), direction: "Paid", partyType: "Vendor", party: "Sanghvi Steels", reference: "PO-2026-00001", mode: "NEFT", amount: 196000, remarks: "Against GRN-2026-00001" },
    { id: "pay4", voucherNo: "PV-2026-00002", date: iso(1), direction: "Paid", partyType: "Vendor", party: "Pune Heat Treaters", reference: "JW-2026-00001", mode: "UPI", amount: 18500, remarks: "Job work charges" },
  ];

  const expenses: OpsState["expenses"] = [
    { id: "ex1", voucherNo: "EX-2026-00001", date: iso(7), category: "Power & Fuel", costCenter: "Press Shop", description: "MSEDCL bill — June", amount: 218400, paidBy: "Meera Shah", mode: "NEFT" },
    { id: "ex2", voucherNo: "EX-2026-00002", date: iso(4), category: "Repairs & Maintenance", costCenter: "Machine Shop", description: "CNC spindle bearing replacement", amount: 42000, paidBy: "Meera Shah", mode: "RTGS" },
    { id: "ex3", voucherNo: "EX-2026-00003", date: iso(2), category: "Freight Outward", costCenter: "Dispatch", description: "VRL Logistics — July lot", amount: 16800, paidBy: "Meera Shah", mode: "UPI" },
    { id: "ex4", voucherNo: "EX-2026-00004", date: iso(1), category: "Canteen", costCenter: "Administration", description: "Weekly canteen settlement", amount: 9400, paidBy: "Admin Desk", mode: "Cash" },
  ];

  const gatePasses: OpsState["gatePasses"] = [
    { id: "gp1", gpNo: "GP-2026-00001", date: iso(3), direction: "Outward", type: "Returnable", party: "Pune Heat Treaters", itemDescription: "MS Round Bar for hardening", quantity: 400, vehicleNo: "MH12 GH 3321", issuedBy: "Security Desk", status: "Open" },
    { id: "gp2", gpNo: "GP-2026-00002", date: iso(1), direction: "Outward", type: "Non-Returnable", party: "Endurance Technologies", itemDescription: "FG cartons — DN-2026-00004", quantity: 24, vehicleNo: "MH12 XY 1120", issuedBy: "Security Desk", status: "Closed" },
    { id: "gp3", gpNo: "GP-2026-00003", date: iso(0), direction: "Inward", type: "Returnable", party: "Precision Metrology Pune", itemDescription: "Calibrated micrometer return", quantity: 1, vehicleNo: "-", issuedBy: "Security Desk", status: "Returned" },
  ];

  const visitors: OpsState["visitors"] = [
    { id: "vs1", date: iso(1), name: "Amit Deshpande", company: "Tata Autocomp Systems", whomToMeet: "Ravi Kulkarni", purpose: "Supplier audit", inTime: "10:15", outTime: "13:40", badgeNo: "V-014", vehicleNo: "MH12 QQ 7788" },
    { id: "vs2", date: iso(0), name: "S. Ramanathan", company: "QMS Consultants", whomToMeet: "Prakash Jadhav", purpose: "ISO surveillance prep", inTime: "09:05", outTime: "", badgeNo: "V-021", vehicleNo: "-" },
  ];

  const assets: OpsState["assets"] = [
    { id: "as1", assetCode: "AST-001", name: "Forklift 2T", category: "Material Handling", location: "FG Store", purchaseDate: "2021-03-10", value: 850000, custodian: "Store In-charge", status: "In Use" },
    { id: "as2", assetCode: "AST-002", name: "Air Compressor 15HP", category: "Utility", location: "Utility Room", purchaseDate: "2019-08-25", value: 320000, custodian: "Ganesh More", status: "In Use" },
    { id: "as3", assetCode: "AST-003", name: "Tempo Traveller", category: "Vehicle", location: "Gate", purchaseDate: "2022-12-01", value: 1650000, custodian: "Admin Desk", status: "In Use" },
    { id: "as4", assetCode: "AST-004", name: "Office Laptop Batch 2020", category: "IT", location: "Admin Block", purchaseDate: "2020-05-14", value: 240000, custodian: "Admin Desk", status: "Under Repair" },
  ];

  const adminServices: OpsState["adminServices"] = [
    { id: "ad1", date: iso(2), service: "Uniform", description: "Shop floor uniform issue — monsoon set", department: "Production", quantity: 24, cost: 28800, handledBy: "Admin Desk", status: "Completed" },
    { id: "ad2", date: iso(1), service: "Canteen", description: "Weekly meal count reconciliation", department: "All", quantity: 412, cost: 9400, handledBy: "Admin Desk", status: "Completed" },
    { id: "ad3", date: iso(0), service: "Housekeeping", description: "Deep cleaning — QC lab before audit", department: "Quality", quantity: 1, cost: 3500, handledBy: "Admin Desk", status: "In Progress" },
  ];

  const leads: OpsState["leads"] = [
    { id: "ld1", enquiryNo: "ENQ-2026-00001", date: iso(14), customerName: "Varroc Engineering", contact: "9890011223", productInterest: "Sheet Metal Bracket A", expectedQty: 25000, estimatedValue: 2400000, source: "Referral", owner: "Meera Shah", status: "Quoted", nextFollowUp: iso(-3) },
    { id: "ld2", enquiryNo: "ENQ-2026-00002", date: iso(8), customerName: "Kalyani Technoforge", contact: "9860044556", productInterest: "MS Hex Bolt M12", expectedQty: 200000, estimatedValue: 3700000, source: "Exhibition", owner: "Meera Shah", status: "Negotiation", nextFollowUp: iso(-1) },
    { id: "ld3", enquiryNo: "ENQ-2026-00003", date: iso(3), customerName: "Spark Minda", contact: "9922077889", productInterest: "Bracket B", expectedQty: 8000, estimatedValue: 896000, source: "Website", owner: "Ravi Kulkarni", status: "Contacted", nextFollowUp: iso(-2) },
    { id: "ld4", enquiryNo: "ENQ-2026-00004", date: iso(1), customerName: "Gabriel India", contact: "9765512340", productInterest: "Hex Nut M12", expectedQty: 150000, estimatedValue: 1087500, source: "Cold Call", owner: "Meera Shah", status: "New", nextFollowUp: iso(-4) },
  ];

  const approvals: OpsState["approvals"] = [
    {
      id: "aw1",
      refNo: "APR-2026-00001",
      date: iso(2),
      type: "Purchase Indent",
      subject: "PR-2026-00004 — MS Round Bar 12mm, 800 kg",
      requester: "Sunil Patil",
      amount: 392000,
      currentStage: 1,
      status: "Pending",
      stages: [
        { role: "Supervisor", by: "Sunil Patil", decision: "Approved", on: iso(2), remarks: "Urgent for SO-2026-00004" },
        { role: "Department Head", by: "", decision: "Pending", on: "", remarks: "" },
        { role: "Accounts", by: "", decision: "Pending", on: "", remarks: "" },
        { role: "Managing Director", by: "", decision: "Pending", on: "", remarks: "" },
      ],
    },
    {
      id: "aw2",
      refNo: "APR-2026-00002",
      date: iso(1),
      type: "Leave",
      subject: "Earned leave — Sunil Patil, 5 days",
      requester: "Sunil Patil",
      amount: 0,
      currentStage: 2,
      status: "Pending",
      stages: [
        { role: "Supervisor", by: "Plant Head", decision: "Approved", on: iso(1), remarks: "Shift cover arranged" },
        { role: "Department Head", by: "Plant Head", decision: "Approved", on: iso(1), remarks: "" },
        { role: "HR", by: "", decision: "Pending", on: "", remarks: "" },
        { role: "Managing Director", by: "", decision: "Pending", on: "", remarks: "" },
      ],
    },
    {
      id: "aw3",
      refNo: "APR-2026-00003",
      date: iso(5),
      type: "Price Approval",
      subject: "QT-2026-00003 — 4% special discount, Varroc",
      requester: "Meera Shah",
      amount: 2400000,
      currentStage: 4,
      status: "Approved",
      stages: [
        { role: "Supervisor", by: "Meera Shah", decision: "Approved", on: iso(5), remarks: "" },
        { role: "Department Head", by: "Plant Head", decision: "Approved", on: iso(5), remarks: "" },
        { role: "Accounts", by: "Meera Shah", decision: "Approved", on: iso(4), remarks: "Margin 21%" },
        { role: "Managing Director", by: "Ravi Kulkarni", decision: "Approved", on: iso(4), remarks: "Go ahead" },
      ],
    },
  ];

  return {
    machines,
    productionPlans,
    designRequests,
    inspections,
    ncrs,
    complaints,
    calibrations,
    maintenancePlans,
    breakdowns,
    spares,
    dispatches,
    employees,
    attendance,
    leaves,
    trainings,
    appraisals,
    payments,
    expenses,
    gatePasses,
    visitors,
    assets,
    adminServices,
    leads,
    approvals,
    notifications: [],
  };
}
