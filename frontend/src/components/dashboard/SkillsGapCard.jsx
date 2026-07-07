import PropTypes from 'prop-types'

export function SkillsGapCard({ missingSkills = [], transferableSkills = [], suggestions = [] }) {
  const hasMissing = missingSkills.length > 0
  const hasTransferable = transferableSkills.length > 0

  return (
    <section className="rounded-3xl border border-gray-800 bg-gray-900 p-6">
      <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-gray-500">Skills gap</h3>
      <div className="mt-5 grid gap-6 md:grid-cols-2">
        <div>
          <p className="text-sm font-semibold text-red-300">Missing</p>
          {hasMissing ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {missingSkills.map((skill) => (
                <span key={skill} className="rounded-full bg-red-100 px-3 py-1 text-xs font-semibold text-red-700">
                  {skill}
                </span>
              ))}
            </div>
          ) : (
            <p className="mt-2 text-sm text-gray-400">No clear hard gaps were identified.</p>
          )}
        </div>

        <div>
          <p className="text-sm font-semibold text-blue-300">You have related experience in</p>
          {hasTransferable ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {transferableSkills.map((skill) => (
                <span key={skill} className="rounded-full bg-blue-100 px-3 py-1 text-xs font-semibold text-blue-700">
                  {skill}
                </span>
              ))}
            </div>
          ) : (
            <p className="mt-2 text-sm text-gray-400">No closely related skills were surfaced.</p>
          )}
        </div>
      </div>

      <div className="mt-6">
        <p className="text-sm font-semibold text-white">Suggestions</p>
        {suggestions.length > 0 ? (
          <ul className="mt-3 space-y-3">
            {suggestions.map((item) => (
              <li
                key={`${item.skill}-${item.resource_type}-${item.note}`}
                className="rounded-2xl border border-gray-800 bg-gray-950 p-4 text-sm text-gray-300"
              >
                <span className="font-semibold text-white">{item.skill}</span>
                {' '}
                <span className="text-gray-500">-&gt;</span>
                {' '}
                <span className="font-medium text-blue-300">{item.resource_type}</span>
                {': '}
                {item.note}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-gray-400">No suggestions were generated.</p>
        )}
      </div>
    </section>
  )
}

SkillsGapCard.propTypes = {
  missingSkills: PropTypes.arrayOf(PropTypes.string),
  transferableSkills: PropTypes.arrayOf(PropTypes.string),
  suggestions: PropTypes.arrayOf(
    PropTypes.shape({
      skill: PropTypes.string,
      resource_type: PropTypes.string,
      note: PropTypes.string
    })
  )
}
