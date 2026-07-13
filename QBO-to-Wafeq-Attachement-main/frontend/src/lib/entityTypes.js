// Maps every raw QBO entity type (SUPPORTED_ENTITY_TYPES in fetcher.py) into a
// tree: direct types + two groups (Expense, Manual Journal) with sub-types.
// Selection always resolves down to raw leaf keys, which get joined into the
// `types=` query param sent to /api/fetch.

export const TYPE_TREE = [
  { key: 'Bill', label: 'Bill' },
  { key: 'Invoice', label: 'Invoice' },
  { key: 'CreditMemo', label: 'Credit Note' },
  { key: 'VendorCredit', label: 'Debit Note' },
  {
    key: 'group-expense', label: 'Expense',
    children: [
      { key: 'Check', label: 'Check' },
      { key: 'Expense', label: 'Expense' },
      { key: 'CreditCardExpense', label: 'Credit Card Expense' },
      { key: 'Purchase', label: 'Purchase (other)' },
    ],
  },
  {
    key: 'group-journal', label: 'Manual Journal',
    children: [
      { key: 'JournalEntry', label: 'Journal Entry' },
      { key: 'Deposit', label: 'Deposit' },
      { key: 'CreditCardCredit', label: 'Credit Card Credit' },
      { key: 'SalesReceipt', label: 'Sales Receipt' },
      { key: 'Expense', label: 'Expense' },
    ],
  },
]

// Some raw types (e.g. "Expense") intentionally appear under more than one
// group in the UI — dedupe here so counts/totals aren't inflated.
export const ALL_LEAVES = [...new Set(
  TYPE_TREE.flatMap((n) => n.children ? n.children.map((c) => c.key) : [n.key])
)]

// raw type → display label (used for scorecard chips / report grouping)
// First occurrence wins — so a type appearing under two groups (e.g. Expense)
// keeps its own group's label rather than the second group's.
export const RAW_TO_LABEL = TYPE_TREE.reduce((acc, n) => {
  if (n.children) n.children.forEach((c) => { if (!(c.key in acc)) acc[c.key] = n.label })
  else if (!(n.key in acc)) acc[n.key] = n.label
  return acc
}, {})
