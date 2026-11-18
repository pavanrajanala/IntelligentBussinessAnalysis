// Shop name, shop type and who the customers are. Used by sign up and by the account page.
export default function ShopFields({ value, onChange, meta }) {
  const set = (patch) => onChange({ ...value, ...patch })
  const toggle = (id) =>
    set({ customer_mix: value.customer_mix.includes(id) ? value.customer_mix.filter((x) => x !== id) : [...value.customer_mix, id] })

  return (
    <>
      <div className="field">
        <label htmlFor="shop-name">Shop name</label>
        <input id="shop-name" className="input" value={value.business_name} onChange={(e) => set({ business_name: e.target.value })} autoComplete="organization" />
      </div>
      <div className="field">
        <label htmlFor="shop-type">What kind of shop is it?</label>
        <select id="shop-type" className="select" value={value.business_type} onChange={(e) => set({ business_type: e.target.value })}>
          <option value="">Choose one</option>
          {meta.business_types.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>
      <fieldset className="field" style={{ border: 0, padding: 0, margin: '0 0 18px' }}>
        <legend className="label" style={{ fontWeight: 600, fontSize: 15, padding: 0, marginBottom: 6 }}>
          Who shops with you?
        </legend>
        <p className="hint" style={{ marginBottom: 8 }}>
          Pick all that apply. We use this to suggest what to keep in front.
        </p>
        <div className="choices">
          {meta.customer_types.map((c) => (
            <label key={c.id} className="choice">
              <input type="checkbox" checked={value.customer_mix.includes(c.id)} onChange={() => toggle(c.id)} />
              <span>{c.label}</span>
            </label>
          ))}
        </div>
      </fieldset>
    </>
  )
}
