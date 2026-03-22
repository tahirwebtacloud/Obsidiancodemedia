import { MetricsChart } from "@/components/evolution/MetricsChart"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { AlertCircle, TrendingUp } from "lucide-react"

export default function EvolutionDashboard() {
  return (
    <div className="container mx-auto p-6 space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Evolution</h1>
        <p className="text-gray-400">Mathematical progression of your content strategy.</p>
      </div>

      {/* Metrics Chart */}
      <MetricsChart />

      {/* Winning Callouts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-8">
        
        {/* Winning Hook */}
        <Card className="bg-gradient-to-br from-[#1A1A1A] to-[#0a0a0a] border-[#F9C74F] border-2 shadow-[0_0_15px_rgba(249,199,79,0.15)] relative overflow-hidden">
          <div className="absolute top-0 left-0 w-1 h-full bg-[#F9C74F]" />
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2 mb-1">
              <TrendingUp className="text-[#F9C74F] h-5 w-5" />
              <CardTitle className="text-white text-lg">Winning Hook</CardTitle>
            </div>
            <CardDescription className="text-gray-400 text-sm">
              Highest conversion from view to click-through (12.4%)
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="p-4 bg-black/50 rounded border border-[#333] mt-2">
              <p className="text-xl font-bold text-white leading-snug">
                "The biggest lie you've been told about [Industry]..."
              </p>
            </div>
            <div className="mt-4 flex gap-4 text-sm">
              <div className="flex flex-col">
                <span className="text-gray-500">Impressions</span>
                <span className="text-white font-mono font-semibold">45.2k</span>
              </div>
              <div className="flex flex-col">
                <span className="text-gray-500">Engagements</span>
                <span className="text-[#F9C74F] font-mono font-semibold">1,240</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Winning CTA */}
        <Card className="bg-gradient-to-br from-[#1A1A1A] to-[#0a0a0a] border-[#4F46E5] border-2 shadow-[0_0_15px_rgba(79,70,229,0.15)] relative overflow-hidden">
          <div className="absolute top-0 left-0 w-1 h-full bg-[#4F46E5]" />
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2 mb-1">
              <AlertCircle className="text-[#4F46E5] h-5 w-5" />
              <CardTitle className="text-white text-lg">Winning CTA</CardTitle>
            </div>
            <CardDescription className="text-gray-400 text-sm">
              Highest outbound click rate (4.8%)
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="p-4 bg-black/50 rounded border border-[#333] mt-2">
              <p className="text-xl font-bold text-white leading-snug">
                "Drop a 🚀 in the comments and I'll DM you the raw template."
              </p>
            </div>
            <div className="mt-4 flex gap-4 text-sm">
              <div className="flex flex-col">
                <span className="text-gray-500">Profile Clicks</span>
                <span className="text-white font-mono font-semibold">843</span>
              </div>
              <div className="flex flex-col">
                <span className="text-gray-500">Leads Gen</span>
                <span className="text-[#4F46E5] font-mono font-semibold">112</span>
              </div>
            </div>
          </CardContent>
        </Card>

      </div>
    </div>
  )
}
