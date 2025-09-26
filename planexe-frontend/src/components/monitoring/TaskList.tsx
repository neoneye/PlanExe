/**
 * Author: Cascade
 * Date: 2025-09-21T11:41:06-04:00
 * PURPOSE: A detailed, real-time task list component that displays the status of all 61 pipeline tasks, grouped by phase.
 * This component provides a transparent and informative view of the plan generation process.
 * SRP and DRY check: Pass - This component's single responsibility is to render the list of tasks and their statuses. It is designed to be reusable and configurable.
 */

'use client';

import React from 'react';
import { TaskPhase, TaskStatus } from '@/lib/types/pipeline';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { CheckCircle, RefreshCw, XCircle, Clock } from 'lucide-react';

// Helper to get the right icon for each task status
const statusIcons: Record<TaskStatus, React.ReactNode> = {
  pending: <Clock className="h-4 w-4 text-gray-400" />,
  running: <RefreshCw className="h-4 w-4 text-blue-500 animate-spin" />,
  completed: <CheckCircle className="h-4 w-4 text-green-500" />,
  failed: <XCircle className="h-4 w-4 text-red-500" />,
};

interface TaskListProps {
  phases: TaskPhase[];
}

export const TaskList: React.FC<TaskListProps> = ({ phases }) => {
  if (!phases || phases.length === 0) {
    return (
      <Card>
        <CardContent className="text-center py-12">
          <p className="text-gray-500">Waiting for pipeline tasks to be initialized...</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Detailed Pipeline Progress</CardTitle>
      </CardHeader>
      <CardContent>
        <Accordion type="multiple" defaultValue={phases.map(p => p.name)} className="w-full">
          {phases.map((phase) => (
            <AccordionItem value={phase.name} key={phase.name}>
              <AccordionTrigger>
                <div className="flex items-center justify-between w-full pr-4">
                  <span className="font-medium">{phase.name}</span>
                  <span className="text-sm text-gray-500">
                    {phase.completedTasks} / {phase.totalTasks} tasks completed
                  </span>
                </div>
              </AccordionTrigger>
              <AccordionContent>
                <ul className="space-y-2 pl-4">
                  {phase.tasks.map((task) => (
                    <li key={task.id} className="flex items-center space-x-3">
                      {statusIcons[task.status]}
                      <span className={`flex-1 ${task.status === 'completed' ? 'text-gray-500 line-through' : ''}`}>
                        {task.name}
                      </span>
                    </li>
                  ))}
                </ul>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </CardContent>
    </Card>
  );
};
