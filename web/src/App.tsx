import { useEffect, useState } from 'react'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

function App() {
  const [apiStatus, setApiStatus] = useState('확인 중...')

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(String(res.status)))))
      .then((body: { status: string }) => setApiStatus(body.status))
      .catch(() => setApiStatus('연결 실패'))
  }, [])

  return (
    <main>
      <h1>book-flow</h1>
      <p>API 상태: {apiStatus}</p>
    </main>
  )
}

export default App
