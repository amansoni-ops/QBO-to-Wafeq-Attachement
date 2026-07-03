import { useState } from 'react'
import { TYPE_TREE, ALL_LEAVES } from '../lib/entityTypes'
import { Ic } from './ui'

function groupState(children, selected) {
  const n = children.filter((c) => selected.has(c.key)).length
  if (n === 0) return 'none'
  if (n === children.length) return 'all'
  return 'partial'
}

export default function EntityTypeSelector({ selected, onChange }) {
  const [open, setOpen] = useState({})

  const allState = groupState(ALL_LEAVES.map((k) => ({ key: k })), selected)

  function toggleAll() {
    onChange(allState === 'all' ? new Set() : new Set(ALL_LEAVES))
  }
  function toggleLeaf(key) {
    const next = new Set(selected)
    next.has(key) ? next.delete(key) : next.add(key)
    onChange(next)
  }
  function toggleGroup(children) {
    const st = groupState(children, selected)
    const next = new Set(selected)
    if (st === 'all') children.forEach((c) => next.delete(c.key))
    else children.forEach((c) => next.add(c.key))
    onChange(next)
  }

  return (
    <div className="type-tree">
      <div className="type-row type-master" onClick={toggleAll}>
        <TriBox state={allState} />
        <span className="tlabel">All Types</span>
        <span className="tcount">{selected.size}/{ALL_LEAVES.length}</span>
      </div>

      {TYPE_TREE.map((node) => {
        if (!node.children) {
          return (
            <div key={node.key} className="type-row" onClick={() => toggleLeaf(node.key)}>
              <TriBox state={selected.has(node.key) ? 'all' : 'none'} />
              <span className="tlabel">{node.label}</span>
            </div>
          )
        }
        const st = groupState(node.children, selected)
        const isOpen = !!open[node.key]
        return (
          <div key={node.key} className="type-group">
            <div className="type-row">
              <span onClick={() => toggleGroup(node.children)} style={{ display: 'flex', alignItems: 'center', gap: 9, flex: 1 }}>
                <TriBox state={st} />
                <span className="tlabel">{node.label}</span>
                <span className="tcount">{node.children.filter((c) => selected.has(c.key)).length}/{node.children.length}</span>
              </span>
              <button className="texpand" onClick={() => setOpen((o) => ({ ...o, [node.key]: !o[node.key] }))}>
                <Ic name={isOpen ? 'chevron-up' : 'chevron-down'} />
              </button>
            </div>
            {isOpen && (
              <div className="type-children">
                {node.children.map((c) => (
                  <div key={c.key} className="type-row type-child" onClick={() => toggleLeaf(c.key)}>
                    <TriBox state={selected.has(c.key) ? 'all' : 'none'} />
                    <span className="tlabel">{c.label}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

function TriBox({ state }) {
  return (
    <span className={`tribox ${state}`}>
      {state === 'all' && <Ic name="check" />}
      {state === 'partial' && <Ic name="minus" />}
    </span>
  )
}
