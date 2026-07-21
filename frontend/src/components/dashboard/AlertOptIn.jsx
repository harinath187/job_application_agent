import { useState } from 'react'
import PropTypes from 'prop-types'
import { Bell, BellOff } from 'lucide-react'
import { Button } from '../ui/Button.jsx'
import { agentApi } from '../../api/agentApi.js'

export function AlertOptIn({ isComplete, alertsEnabled, alertEmail, alertMessage, alertDisabledByUser, onAlertsToggled }) {
  const [toggling, setToggling] = useState(false)
  const [toggleError, setToggleError] = useState('')

  if (!isComplete) {
    return null
  }

  const heading = alertsEnabled
    ? 'Email alerts enabled automatically'
    : alertDisabledByUser
      ? 'Email alerts disabled'
      : 'Email alerts not enabled'

  const defaultMessage = alertsEnabled
    ? `New job matches will be sent to ${alertEmail}.`
    : alertDisabledByUser
      ? `You disabled email alerts for ${alertEmail}.`
      : 'No email address was found in the uploaded resume.'

  const handleToggle = async () => {
    if (!alertEmail) return
    setToggling(true)
    setToggleError('')
    try {
      await agentApi.toggleAlerts({ email: alertEmail, active: !alertsEnabled })
      onAlertsToggled?.(!alertsEnabled)
    } catch (err) {
      setToggleError('Unable to update alert settings. Please try again.')
    } finally {
      setToggling(false)
    }
  }

  return (
    <section className="rounded-3xl border border-slate-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-xl shadow-black/5 dark:shadow-black/20">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-4">
          <div className={`flex h-12 w-12 items-center justify-center rounded-2xl text-white ${alertsEnabled ? 'bg-emerald-700' : 'bg-amber-700'}`}>
            {alertsEnabled ? '@' : '!'}
          </div>
          <div>
            <p className="text-sm uppercase tracking-[0.24em] text-indigo-600 dark:text-indigo-300">Job Alerts</p>
            <h2 className="mt-2 text-xl font-semibold text-indigo-600 dark:text-indigo-300">
              {heading}
            </h2>
            <p className="mt-2 text-sm text-slate-600 dark:text-gray-400">
              {alertMessage || defaultMessage}
            </p>
            {alertEmail && <p className="mt-3 text-sm text-indigo-600 dark:text-indigo-300">{alertEmail}</p>}
            {toggleError && <p className="mt-2 text-sm text-red-600 dark:text-red-400">{toggleError}</p>}
          </div>
        </div>
        {alertEmail && (
          <Button
            onClick={handleToggle}
            variant={alertsEnabled ? 'secondary' : 'primary'}
            disabled={toggling}
            loading={toggling}
          >
            {alertsEnabled ? <BellOff size={16} /> : <Bell size={16} />}
            {alertsEnabled ? 'Disable Alerts' : 'Enable Alerts'}
          </Button>
        )}
      </div>
    </section>
  )
}

AlertOptIn.propTypes = {
  isComplete: PropTypes.bool,
  alertsEnabled: PropTypes.bool,
  alertEmail: PropTypes.string,
  alertMessage: PropTypes.string,
  alertDisabledByUser: PropTypes.bool,
  onAlertsToggled: PropTypes.func
}
