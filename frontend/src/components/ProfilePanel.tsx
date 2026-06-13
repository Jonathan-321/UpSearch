import { useEffect, useMemo, useState } from 'react'
import type { OSProfileHarness, OSUserProfile } from '../hooks/useOS'

interface Props {
  content: string
  profile: OSUserProfile | null
  harness: OSProfileHarness | null
  fetching: boolean
  onSave: (content: string) => Promise<void>
  onFetchSources: () => Promise<void>
}

const PROFILE_TEMPLATE = `Start with one public source:
Website:

Optional:
GitHub:
LinkedIn:
Resume URL:

Goal:
- Roles, research areas, or opportunities you want UpSearch to prioritize

Constraints:
- Visa / sponsorship:
- Location:
- Timeframe:`

function profileName(content: string, profile: OSUserProfile | null, harness: OSProfileHarness | null): string {
  if (profile?.name) return profile.name
  if (harness?.profile_name) return harness.profile_name
  const match = content.match(/^Name:\s*(.+)$/im)
  return match?.[1]?.trim() || 'New user'
}

function profileSchool(content: string, profile: OSUserProfile | null, harness: OSProfileHarness | null): string {
  if (profile?.school) return profile.school
  if (harness?.school) return harness.school
  const match = content.match(/^School:[ \t]*(.+)$/im)
  return match?.[1]?.trim() || 'Identity inferred from public evidence'
}

function ChipList({ items, empty }: { items: string[]; empty: string }) {
  if (!items.length) return <em>{empty}</em>
  return (
    <div className="profile-chip-list">
      {items.map(item => <span key={item}>{item}</span>)}
    </div>
  )
}

function sourceValue(value: string): string {
  if (!value || value === 'not provided') return value
  try {
    const parsed = new URL(value)
    const host = parsed.hostname.replace(/^www\./, '')
    const path = parsed.pathname === '/' ? '' : parsed.pathname.replace(/\/$/, '')
    return `${host}${path}`
  } catch {
    return value
  }
}

export default function ProfilePanel({ content, profile, harness, fetching, onSave, onFetchSources }: Props) {
  const [draft, setDraft] = useState(content)
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    setDraft(content)
  }, [content])

  const name = useMemo(() => profileName(content, profile, harness), [content, profile, harness])
  const school = useMemo(() => profileSchool(content, profile, harness), [content, profile, harness])
  const configured = content.trim().length > 0
  const changed = draft.trim() !== content.trim()
  const fetchableSources = harness?.sources.filter(source => source.status === 'needs_fetch') ?? []

  return (
    <section className="profile-panel" aria-label="Active user profile">
      <div className="profile-panel-summary">
        <div>
          <p className="studio-kicker">Active profile</p>
          <h2>{configured ? name : 'Set up the user profile'}</h2>
          <span>{configured ? school : 'New users start here before sourcing companies.'}</span>
        </div>
        <div className="profile-panel-actions">
          {configured && <span className="badge">Used by every agent</span>}
          {harness && <span className="badge badge-accent">{harness.route_provider} · {harness.route_model}</span>}
          {harness?.fetched_at && <span className="badge badge-success">Sources fetched</span>}
          <button
            className="btn btn-ghost"
            type="button"
            disabled={!fetchableSources.length || fetching}
            onClick={onFetchSources}
          >
            {fetching ? 'Fetching sources' : fetchableSources.length ? 'Fetch public sources' : 'Sources current'}
          </button>
          <button className="btn btn-ghost" type="button" onClick={() => setOpen(value => !value)}>
            {open ? 'Hide profile' : configured ? 'Edit profile' : 'Create profile'}
          </button>
        </div>
      </div>

      {harness && (
        <div className="profile-harness-grid">
          <div>
            <span>Source inputs</span>
            <div className="profile-source-list">
              {harness.sources.map(source => (
                <p key={`${source.kind}-${source.value}`}>
                  <strong>{source.kind}</strong>
                  <span>
                    {sourceValue(source.value)}
                    {source.discovered_from ? ` via ${sourceValue(source.discovered_from)}` : ''}
                  </span>
                  <em className={`is-${source.status.replace(/_/g, '-')}`}>{source.status}</em>
                </p>
              ))}
            </div>
          </div>
          <div>
            <span>Proof bank</span>
            <ChipList items={harness.proof_bank} empty="No proof extracted yet" />
          </div>
          <div>
            <span>Target lanes</span>
            <ChipList items={harness.target_lanes} empty="No target lanes set" />
          </div>
          <div>
            <span>Do not claim</span>
            <ChipList items={harness.claim_boundaries} empty="No claim boundaries set" />
          </div>
          {harness.source_warnings && harness.source_warnings.length > 0 && (
            <div>
              <span>Fetch warnings</span>
              <ChipList items={harness.source_warnings} empty="No source warnings" />
            </div>
          )}
        </div>
      )}

      {open && (
        <div className="profile-editor">
          <div className="profile-editor-copy">
            <strong>How new users interact</strong>
            <p>
              One public source is enough to begin. UpSearch follows relevant links, reads supported
              resumes, and assembles a reviewable profile before it researches opportunities.
            </p>
          </div>
          <textarea
            value={draft || PROFILE_TEMPLATE}
            onChange={event => {
              setDraft(event.target.value)
              setSaved(false)
            }}
            rows={14}
            aria-label="User profile text"
            spellCheck={false}
          />
          <div className="profile-editor-footer">
            <button
              className="btn btn-ghost"
              type="button"
              onClick={() => {
                setDraft(PROFILE_TEMPLATE)
                setSaved(false)
              }}
            >
              Use template
            </button>
            <span>
              {saved ? 'Saved. Future packet runs will use this profile.' : changed ? 'Unsaved changes' : 'Profile current'}
            </span>
            <button
              className="btn btn-primary"
              type="button"
              disabled={saving || !draft.trim() || !changed}
              onClick={async () => {
                setSaving(true)
                try {
                  await onSave(draft)
                  setSaved(true)
                } finally {
                  setSaving(false)
                }
              }}
            >
              {saving ? 'Saving' : 'Save active profile'}
            </button>
          </div>
        </div>
      )}
    </section>
  )
}
