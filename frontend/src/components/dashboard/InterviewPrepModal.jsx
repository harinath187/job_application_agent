import { useEffect, useState } from 'react'
import PropTypes from 'prop-types'
import { Badge } from '../ui/Badge.jsx'
import { Button } from '../ui/Button.jsx'
import { Modal } from '../ui/Modal.jsx'
import { agentApi } from '../../api/agentApi.js'

function categoryVariant(category) {
  if (category === 'technical') return 'interview'
  if (category === 'situational') return 'applied'
  return 'new'
}

export function InterviewPrepModal({ jobId, isOpen, onClose }) {
  const [questions, setQuestions] = useState([])
  const [loadedJobId, setLoadedJobId] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isRegenerating, setIsRegenerating] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const loadQuestions = async () => {
      if (!isOpen || !jobId || loadedJobId === jobId) return
      try {
        setIsLoading(true)
        setError('')
        const data = await agentApi.getJobInterviewPrep(jobId)
        setQuestions(data.questions || [])
        setLoadedJobId(jobId)
      } catch {
        setError('Interview prep unavailable for this job.')
        setQuestions([])
        setLoadedJobId(jobId)
      } finally {
        setIsLoading(false)
      }
    }

    loadQuestions()
  }, [isOpen, jobId, questions.length])

  const handleRegenerate = async () => {
    try {
      setIsRegenerating(true)
      setError('')
      const data = await agentApi.regenerateJobInterviewPrep(jobId)
      setQuestions(data.questions || [])
      setLoadedJobId(jobId)
    } catch {
      setError('Unable to regenerate interview prep.')
    } finally {
      setIsRegenerating(false)
    }
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Interview prep">
      <div className="space-y-5">
        <div className="flex justify-end">
          <Button onClick={handleRegenerate} variant="secondary" disabled={isRegenerating || isLoading}>
            {isRegenerating ? 'Regenerating...' : 'Regenerate questions'}
          </Button>
        </div>

        {isLoading ? (
          <p className="text-sm text-gray-400">Loading interview prep...</p>
        ) : error ? (
          <p className="text-sm text-red-300">{error}</p>
        ) : questions.length === 0 ? (
          <p className="text-sm text-gray-400">Interview prep unavailable for this job.</p>
        ) : (
          <div className="space-y-3">
            {questions.map((item, index) => (
              <details key={`${item.question}-${index}`} className="rounded-2xl border border-gray-800 bg-gray-950 p-4">
                <summary className="cursor-pointer list-none">
                  <div className="flex flex-wrap items-center gap-3">
                    <Badge label={item.category} variant={categoryVariant(item.category)} />
                    <span className="font-semibold text-white">{item.question}</span>
                  </div>
                </summary>
                <div className="mt-4 space-y-3 pl-1 text-sm text-gray-300">
                  <p>{item.model_answer}</p>
                  <p className="italic text-gray-400">{item.tip}</p>
                </div>
              </details>
            ))}
          </div>
        )}
      </div>
    </Modal>
  )
}

InterviewPrepModal.propTypes = {
  jobId: PropTypes.string,
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired
}
