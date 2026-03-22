"use client"

import React, { useMemo } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart
} from 'recharts'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

const mockData = [
  { name: 'Mon', impressions: 4000, engagement: 240 },
  { name: 'Tue', impressions: 3000, engagement: 139 },
  { name: 'Wed', impressions: 2000, engagement: 980 },
  { name: 'Thu', impressions: 2780, engagement: 390 },
  { name: 'Fri', impressions: 5890, engagement: 480 },
  { name: 'Sat', impressions: 8390, engagement: 380 },
  { name: 'Sun', impressions: 11490, engagement: 430 },
]

export function MetricsChart() {
  return (
    <Card className="bg-[#0E0E0E] border-[#2A2A2A] text-white">
      <CardHeader>
        <CardTitle className="text-[#F9C74F]">Impression Growth</CardTitle>
        <CardDescription className="text-gray-400">
          7-day performance across generated content
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-[300px] w-full mt-4">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={mockData}
              margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
            >
              <defs>
                <linearGradient id="colorImpressions" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#F9C74F" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#F9C74F" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#2A2A2A" vertical={false} />
              <XAxis 
                dataKey="name" 
                stroke="#666" 
                tick={{ fill: '#888' }} 
                tickLine={false}
                axisLine={false}
              />
              <YAxis 
                stroke="#666" 
                tick={{ fill: '#888' }} 
                tickLine={false}
                axisLine={false}
                tickFormatter={(value) => `${value / 1000}k`}
              />
              <Tooltip 
                contentStyle={{ backgroundColor: '#1A1A1A', borderColor: '#333', color: '#fff' }}
                itemStyle={{ color: '#F9C74F' }}
              />
              <Area 
                type="monotone" 
                dataKey="impressions" 
                stroke="#F9C74F" 
                strokeWidth={3}
                fillOpacity={1} 
                fill="url(#colorImpressions)" 
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}
