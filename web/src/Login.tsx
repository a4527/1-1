import { useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError, login, signup } from './api'
import type { User } from './api'

export default function Login({ onDone }: { onDone: (user: User) => void }) {
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!email.trim() || password.length < 8) {
      setError('이메일을 입력하고, 비밀번호는 8자 이상으로 적어 주세요.')
      return
    }
    setBusy(true)
    setError('')
    try {
      onDone(await (mode === 'login' ? login : signup)(email.trim(), password))
    } catch (err) {
      const status = err instanceof ApiError ? err.status : 0
      if (status === 401) setError('이메일 또는 비밀번호가 맞지 않습니다.')
      else if (status === 409) setError('이미 가입된 이메일입니다. 로그인해 주세요.')
      else if (status === 422) setError('이메일 형식과 비밀번호(8자 이상)를 확인해 주세요.')
      else setError('요청하지 못했습니다. API 서버가 켜져 있는지 확인하세요.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth">
      <form className="auth-card" onSubmit={handleSubmit}>
        <h1>Task Flow</h1>
        <h2>{mode === 'login' ? '로그인' : '가입'}</h2>
        <label>
          이메일
          <input type="email" autoFocus value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          비밀번호 (8자 이상)
          <input
            type="password"
            value={password}
            maxLength={128}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {error && (
          <p className="field-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" disabled={busy}>
          {mode === 'login' ? '로그인' : '가입하고 시작'}
        </button>
        <button
          type="button"
          className="link"
          onClick={() => {
            setMode(mode === 'login' ? 'signup' : 'login')
            setError('')
          }}
        >
          {mode === 'login' ? '계정이 없나요? 가입' : '이미 계정이 있나요? 로그인'}
        </button>
      </form>
    </div>
  )
}
