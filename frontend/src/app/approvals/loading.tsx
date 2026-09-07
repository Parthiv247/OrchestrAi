import { Loader2 } from 'lucide-react'
export default function Loading() {
  return (
    <div className="flex items-center justify-center h-full min-h-96">
      <Loader2 size={32} className="animate-spin" style={{ color: '#38BDF8' }} />
    </div>
  )
}