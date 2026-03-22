import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function IntelligenceDashboard() {
  return (
    <div className="container mx-auto p-6 space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Intelligence</h1>
        <p className="text-gray-400">Monitor viral trends and competitor analysis in real-time.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Viral Posts Section */}
        <Card className="bg-[#0E0E0E] border-[#2A2A2A] text-white">
          <CardHeader>
            <CardTitle className="text-[#F9C74F]">Viral Posts</CardTitle>
            <CardDescription className="text-gray-400">
              Top performing content across your industry graph
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="p-4 rounded-md bg-[#1A1A1A] border border-[#333] flex justify-between items-center">
              <div>
                <p className="font-semibold">"Why 99% of startups fail at AI..."</p>
                <p className="text-sm text-gray-400 mt-1">Found 2 hours ago • Tech sector</p>
              </div>
              <div className="text-right">
                <span className="text-[#F9C74F] font-bold">8.4k</span>
                <p className="text-xs text-gray-500">Likes</p>
              </div>
            </div>
            
            <div className="p-4 rounded-md bg-[#1A1A1A] border border-[#333] flex justify-between items-center">
              <div>
                <p className="font-semibold">"Stop using React for everything."</p>
                <p className="text-sm text-gray-400 mt-1">Found 5 hours ago • Dev tools</p>
              </div>
              <div className="text-right">
                <span className="text-[#F9C74F] font-bold">12.1k</span>
                <p className="text-xs text-gray-500">Likes</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Competitor Analysis Section */}
        <Card className="bg-[#0E0E0E] border-[#2A2A2A] text-white">
          <CardHeader>
            <CardTitle className="text-[#F9C74F]">Competitor Analysis</CardTitle>
            <CardDescription className="text-gray-400">
              Activity and strategy shifts from tracked accounts
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="p-4 rounded-md bg-[#1A1A1A] border border-[#333]">
              <div className="flex justify-between items-center mb-2">
                <p className="font-bold text-white">@TechVisionary</p>
                <span className="text-xs px-2 py-1 bg-blue-900/30 text-blue-400 rounded-full border border-blue-800/50">Strategy Shift</span>
              </div>
              <p className="text-sm text-gray-300">Started posting 3x more about "Agents" vs "LLMs". Engagement up 42%.</p>
            </div>
            
            <div className="p-4 rounded-md bg-[#1A1A1A] border border-[#333]">
              <div className="flex justify-between items-center mb-2">
                <p className="font-bold text-white">@BuildInPublic</p>
                <span className="text-xs px-2 py-1 bg-green-900/30 text-green-400 rounded-full border border-green-800/50">Format Trend</span>
              </div>
              <p className="text-sm text-gray-300">Switched to text-only hooks. Carousel usage dropped to 0 this week.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
