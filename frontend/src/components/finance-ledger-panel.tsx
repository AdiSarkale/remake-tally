import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api/client";
import { formatCurrency, formatDate } from "@/lib/format";

interface Account { id: string; code: string; name: string; account_type: string; active: boolean; system_account: boolean; }
interface Mapping {
  salary_expense_account_id: string; salary_payable_account_id: string;
  employee_pf_payable_account_id: string; professional_tax_payable_account_id: string;
  tds_payable_account_id: string;
}
interface JournalLine { id: string; account_id: string; description: string; debit: number; credit: number; }
interface Journal {
  id: string; journal_no: string; entry_date: string; narration: string;
  source_type: string; source_id: string; status: string; reversal_of_id: string | null; lines: JournalLine[];
}

const emptyMapping: Mapping = {
  salary_expense_account_id: "", salary_payable_account_id: "",
  employee_pf_payable_account_id: "", professional_tax_payable_account_id: "",
  tds_payable_account_id: "",
};

export function FinanceLedgerPanel({ canEdit }: { canEdit: boolean }) {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [mapping, setMapping] = useState<Mapping>(emptyMapping);
  const [journals, setJournals] = useState<Journal[]>([]);
  const [accountForm, setAccountForm] = useState({ code: "", name: "", account_type: "expense" });
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const [accountRows, mappingRow, journalRows] = await Promise.all([
        api.get<Account[]>("/finance/accounts"),
        api.get<Mapping>("/finance/payroll-account-mapping"),
        api.get<Journal[]>("/finance/journals"),
      ]);
      setAccounts(accountRows);
      setMapping(mappingRow);
      setJournals(journalRows);
    } catch (err) { toast.error(err instanceof Error ? err.message : "Could not load Finance ledger"); }
  };
  useEffect(() => { void load(); }, []);

  const saveMapping = async () => {
    setBusy(true);
    try { await api.put("/finance/payroll-account-mapping", mapping); toast.success("Payroll ledger mapping saved"); await load(); }
    catch (err) { toast.error(err instanceof Error ? err.message : "Could not save payroll mapping"); }
    finally { setBusy(false); }
  };

  const createAccount = async () => {
    if (!accountForm.code.trim() || !accountForm.name.trim()) { toast.error("Enter account code and name"); return; }
    setBusy(true);
    try {
      await api.post("/finance/accounts", accountForm);
      toast.success("Ledger account created");
      setAccountForm({ code: "", name: "", account_type: "expense" });
      await load();
    } catch (err) { toast.error(err instanceof Error ? err.message : "Could not create account"); }
    finally { setBusy(false); }
  };

  const accountName = (id: string) => {
    const account = accounts.find((row) => row.id === id);
    return account ? account.code + " · " + account.name : "Select account";
  };
  const accountOptions = (type: string) => accounts.filter((row) => row.active && row.account_type === type);

  const mappingFields: [keyof Mapping, string, string][] = [
    ["salary_expense_account_id", "Salary expense", "expense"],
    ["salary_payable_account_id", "Net salary payable", "liability"],
    ["employee_pf_payable_account_id", "Employee PF payable", "liability"],
    ["professional_tax_payable_account_id", "Professional tax payable", "liability"],
    ["tds_payable_account_id", "Salary TDS payable", "liability"],
  ];

  return (
    <section className="space-y-5">
      <header><h2 className="text-lg font-semibold">General Ledger & Payroll Posting</h2><p className="text-sm text-muted-foreground">Payroll finalization creates a balanced salary journal. Reversal creates a linked opposite journal; posted journals are immutable.</p></header>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border p-4 space-y-3">
          <h3 className="font-semibold">Payroll account mapping</h3>
          {mappingFields.map(([key, label, type]) => <label key={key} className="block space-y-1 text-sm"><span>{label}</span><select className="h-9 w-full rounded-md border bg-background px-3" value={mapping[key]} onChange={(e) => setMapping({ ...mapping, [key]: e.target.value })}><option value="">Select {type} account</option>{accountOptions(type).map((row) => <option key={row.id} value={row.id}>{row.code} · {row.name}</option>)}</select></label>)}
          <Button size="sm" disabled={busy || Object.values(mapping).some((value) => !value)} onClick={() => void saveMapping()}>Save payroll mapping</Button>
          <p className="text-xs text-muted-foreground">Expense must map to an expense account; all deductions and net salary must map to distinct liability accounts.</p>
        </div>
        <div className="rounded-lg border p-4 space-y-3">
          <h3 className="font-semibold">Chart of accounts</h3>
          <div className="grid gap-2 sm:grid-cols-2">
            <Input placeholder="Code" value={accountForm.code} onChange={(e) => setAccountForm({ ...accountForm, code: e.target.value.toUpperCase() })} />
            <Input placeholder="Account name" value={accountForm.name} onChange={(e) => setAccountForm({ ...accountForm, name: e.target.value })} />
          </div>
          <div className="flex gap-2"><select className="h-9 flex-1 rounded-md border bg-background px-3" value={accountForm.account_type} onChange={(e) => setAccountForm({ ...accountForm, account_type: e.target.value })}>{["asset", "liability", "equity", "income", "expense"].map((type) => <option key={type}>{type}</option>)}</select><Button size="sm" disabled={busy || !canEdit} onClick={() => void createAccount()}>Add account</Button></div>
          <div className="max-h-44 overflow-auto text-sm">{accounts.map((row) => <div key={row.id} className="flex justify-between gap-2 border-b py-1"><span>{row.code} · {row.name}</span><span className="text-muted-foreground">{row.account_type}</span></div>)}</div>
        </div>
      </div>
      <div className="rounded-lg border p-4 space-y-3">
        <div className="flex items-center justify-between"><h3 className="font-semibold">Journal history</h3><Button size="sm" variant="outline" disabled={busy} onClick={() => void load()}>Refresh</Button></div>
        {journals.length ? <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-sm"><thead><tr className="border-b text-left text-muted-foreground">{["Journal", "Date", "Source", "Narration", "Debit", "Credit", "Reversal of"].map((label) => <th key={label} className="py-2 pr-3">{label}</th>)}</tr></thead><tbody>{journals.map((journal) => {
          const debit = journal.lines.reduce((sum, line) => sum + Number(line.debit), 0);
          const credit = journal.lines.reduce((sum, line) => sum + Number(line.credit), 0);
          return <tr key={journal.id} className="border-b last:border-0"><td className="py-2 pr-3 font-mono">{journal.journal_no}</td><td className="py-2 pr-3">{formatDate(journal.entry_date)}</td><td className="py-2 pr-3">{journal.source_type}</td><td className="py-2 pr-3 max-w-64 truncate" title={journal.narration}>{journal.narration}</td><td className="py-2 pr-3 text-right tabular-nums">{formatCurrency(debit)}</td><td className="py-2 pr-3 text-right tabular-nums">{formatCurrency(credit)}</td><td className="py-2 pr-3 font-mono text-xs">{journal.reversal_of_id || "—"}</td></tr>;
        })}</tbody></table></div> : <p className="text-sm text-muted-foreground">No journals posted yet.</p>}
      </div>
    </section>
  );
}
