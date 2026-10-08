import { ToastProvider } from './components/Toasts'
import { TopBar } from './components/TopBar'
import { AuthProvider } from './components/AuthProvider'
import { MeProvider } from './components/MeProvider'
import { History, Pronunciations, SignIn } from './pages/AccountPages'
import { About, NotFound, Privacy, Terms } from './pages/InfoPages'
import { Studio } from './pages/Studio'
import { usePath } from './lib/router'
import { StatusProvider } from './components/StatusProvider'

const PAGES: Record<string, () => React.JSX.Element | null> = {
  '/': Studio,
  '/about': About,
  '/privacy': Privacy,
  '/terms': Terms,
  '/signin': SignIn,
  '/history': History,
  '/pronunciations': Pronunciations,
}

export default function App() {
  const path = usePath()
  const Page = PAGES[path] ?? NotFound
  return (
    <AuthProvider>
      <MeProvider>
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
      </MeProvider>
    </AuthProvider>
  )
}
