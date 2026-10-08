import { ToastProvider } from './components/Toasts'
import { TopBar } from './components/TopBar'
import { About, NotFound, Privacy, Terms } from './pages/InfoPages'
import { Studio } from './pages/Studio'
import { usePath } from './lib/router'
import { StatusProvider } from './components/StatusProvider'

const PAGES: Record<string, () => React.JSX.Element> = {
  '/': Studio,
  '/about': About,
  '/privacy': Privacy,
  '/terms': Terms,
}

export default function App() {
  const path = usePath()
  const Page = PAGES[path] ?? NotFound
  return (
    <StatusProvider>
      <ToastProvider>
        <div className="app">
          <TopBar />
          <main className="content">
            <Page />
          </main>
        </div>
      </ToastProvider>
    </StatusProvider>
  )
}
