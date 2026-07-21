export function AlertOptIn({ isComplete, alertsEnabled, alertEmail, alertMessage }) {
  if (!isComplete) {
    return null
  }

  return (
    <section className="rounded-3xl border border-slate-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-xl shadow-black/5 dark:shadow-black/20">
      <div className="flex items-start gap-4">
        <div className={`flex h-12 w-12 items-center justify-center rounded-2xl text-white ${alertsEnabled ? 'bg-emerald-700' : 'bg-amber-700'}`}>
          {alertsEnabled ? '@' : '!'}
        </div>
        <div>
          <p className="text-sm uppercase tracking-[0.24em] text-indigo-600 dark:text-indigo-300">Job Alerts</p>
          <h2 className="mt-2 text-xl font-semibold text-indigo-600 dark:text-indigo-300">
            {alertsEnabled ? 'Email alerts enabled automatically' : 'Email alerts not enabled'}
          </h2>
          <p className="mt-2 text-sm text-slate-600 dark:text-gray-400">
            {alertMessage || (alertsEnabled ? `New job matches will be sent to ${alertEmail}.` : 'No email address was found in the uploaded resume.')}
          </p>
          {alertEmail && <p className="mt-3 text-sm text-indigo-600 dark:text-indigo-300">{alertEmail}</p>}
        </div>
      </div>
    </section>
  )
}
