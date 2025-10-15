/**
 * Author: Codex using GPT-5
 * Date: `2025-09-28T21:31:26-04:00`
 * PURPOSE: Renders the primary plan creation workflow, wiring FastAPI-backed model selection, prompt examples, and submission flow into the Next.js UI; integrates shadcn form primitives with shared schema/types so the dashboard stays consistent.
 * SRP and DRY check: Pass - Single component handles plan creation UI; validated against shared form utilities to avoid duplication.
 */

'use client';

import React, { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Form, FormControl, FormDescription, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PlanFormSchema, PlanFormData } from '@/lib/types/forms';
import { CreatePlanRequest, LLMModel, PromptExample } from '@/lib/api/fastapi-client';
import { Loader2 } from 'lucide-react';

interface PlanFormProps {
  onSubmit: (data: CreatePlanRequest) => Promise<void>;
  isSubmitting?: boolean;
  llmModels?: LLMModel[];
  promptExamples?: PromptExample[];
  className?: string;
  modelsError?: string | null;
  isLoadingModels?: boolean;
  loadLLMModels?: (force?: boolean) => Promise<void>;
}

export const PlanForm: React.FC<PlanFormProps> = ({
  onSubmit,
  isSubmitting = false,
  llmModels = [],
  promptExamples = [],
  className = '',
  modelsError = null,
  isLoadingModels = false,
  loadLLMModels
}) => {
  const [selectedExample, setSelectedExample] = useState<string>('');

  const form = useForm<PlanFormData>({
    resolver: zodResolver(PlanFormSchema),
    defaultValues: {
      prompt: '',
      llm_model: '',
      speed_vs_detail: 'all_details_but_slow',
      title: '',
      tags: []
    }
  });

  // Set default model if available
  useEffect(() => {
    if (llmModels.length > 0 && !form.getValues('llm_model')) {
      const defaultModel = llmModels.find(m => m.priority === 1) || llmModels[0];
      form.setValue('llm_model', defaultModel.id);
    }
  }, [llmModels, form]);

  const handleSubmit = async (data: PlanFormData) => {
    const request: CreatePlanRequest = {
      prompt: data.prompt,
      llm_model: data.llm_model,
      speed_vs_detail: data.speed_vs_detail,
    };

    await onSubmit(request);
  };

  const handleExampleSelect = (example: PromptExample) => {
    form.setValue('prompt', example.prompt);
    form.setValue('title', example.title);
    setSelectedExample(example.uuid);
  };

  const speedOptions = [
    {
      value: 'all_details_but_slow' as const,
      label: 'All Details (Slow)',
      description: 'Complete analysis with all 50+ tasks (~60 minutes)',
      duration: '45-90 min'
    },
    {
      value: 'fast_but_skip_details' as const,
      label: 'Fast Mode (Basic)',
      description: 'Essential tasks only for quick results (~15 minutes)',
      duration: '10-20 min'
    }
  ];

  return (
    <div className={`space-y-6 ${className}`}>
      <Card>
        <CardHeader>
          <CardTitle>Create New Plan</CardTitle>
          <CardDescription>
            Describe your project or idea and let AI create a comprehensive plan
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
              
              {/* Prompt Examples Tab */}
              <Tabs defaultValue="create" className="w-full">
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="create">Create Plan</TabsTrigger>
                  <TabsTrigger value="examples">Example Prompts</TabsTrigger>
                </TabsList>
                
                <TabsContent value="create" className="space-y-6">
                  
                  {/* Plan Title */}
                  <FormField
                    control={form.control}
                    name="title"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel htmlFor="plan-title">Plan Title (Optional)</FormLabel>
                        <FormControl>
                          <Input
                            id="plan-title"
                            placeholder="e.g. Website Redesign Project"
                            {...field}
                            disabled={isSubmitting}
                          />
                        </FormControl>
                        <FormDescription>
                          Give your plan a memorable name
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  {/* Main Prompt */}
                  <FormField
                    control={form.control}
                    name="prompt"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel htmlFor="plan-prompt">Plan Description *</FormLabel>
                        <FormControl>
                          <Textarea
                            id="plan-prompt"
                            placeholder="Describe your project, goal, or idea in detail. The more context you provide, the better the plan will be..."
                            className="min-h-[120px]"
                            {...field}
                            disabled={isSubmitting}
                          />
                        </FormControl>
                        <FormDescription>
                          Minimum 10 characters. Be specific about goals, constraints, timeline, and resources.
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  {/* LLM Model Selection */}
                  <FormField
                    control={form.control}
                    name="llm_model"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel htmlFor="llm-model-select">AI Model *</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value} disabled={isSubmitting || isLoadingModels} name="llm_model">
                          <FormControl>
                            <SelectTrigger id="llm-model-select">
                              <SelectValue placeholder={
                                isLoadingModels ? "Loading models..." :
                                modelsError ? "Error loading models" :
                                llmModels.length === 0 ? "No models available" :
                                "Select AI model"
                              } />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {isLoadingModels ? (
                              <SelectItem value="__loading__" disabled>
                                <div className="flex items-center space-x-2">
                                  <Loader2 className="h-4 w-4 animate-spin" />
                                  <span>Loading models from Railway...</span>
                                </div>
                              </SelectItem>
                            ) : modelsError ? (
                              <>
                                <SelectItem value="__error__" disabled>
                                  <div className="flex items-center space-x-2 text-red-600">
                                    <span>[Error] Railway Error: {modelsError}</span>
                                  </div>
                                </SelectItem>
                                <SelectItem value="gpt-5-mini-2025-08-07" >
                                  <div className="flex items-center space-x-2">
                                    <span>Default: GPT-5 Nano (Primary)</span>
                                    <Badge variant="outline" className="text-xs">
                                      Primary Choice
                                    </Badge>
                                  </div>
                                </SelectItem>
                              </>
                            ) : llmModels.length === 0 ? (
                              <>
                                <SelectItem value="__empty__" disabled>
                                  <div className="flex items-center space-x-2 text-orange-600">
                                    <span>[Warning] No models from Railway API</span>
                                  </div>
                                </SelectItem>
                                <SelectItem value="gpt-5-mini-2025-08-07">
                                  <div className="flex items-center space-x-2">
                                    <span>Default: GPT-5 Nano (Primary)</span>
                                    <Badge variant="outline" className="text-xs">
                                      Primary Choice
                                    </Badge>
                                  </div>
                                </SelectItem>
                              </>
                            ) : (
                              llmModels.map((model) => (
                                <SelectItem key={model.id} value={model.id}>
                                  <div className="flex items-center space-x-2">
                                    <span>{model.label ?? model.id}</span>
                                    {model.comment && (
                                      <Badge variant="outline">
                                        {model.comment}
                                      </Badge>
                                    )}
                                  </div>
                                </SelectItem>
                              ))
                            )}
                          </SelectContent>
                        </Select>
                        {modelsError && (
                          <div className="text-red-600 block mt-2 p-2 bg-red-50 rounded">
                            <strong>Railway Debug Info:</strong><br/>
                            - API Error: {modelsError}<br/>
                            - Endpoint: /api/models<br/>
                            - Fallback option available above<br/>
                            {loadLLMModels && (
                              <Button 
                                type="button"
                                variant="outline" 
                                size="sm" 
                                className="mt-2"
                                onClick={() => loadLLMModels(true)}
                                disabled={isLoadingModels}
                              >
                                {isLoadingModels ? "Retrying..." : "Retry Railway Connection"}
                              </Button>
                            )}
                          </div>
                        )}
                        {llmModels.length === 0 && !modelsError && !isLoadingModels && (
                          <div className="text-orange-600 block mt-2 p-2 bg-orange-50 rounded">
                            <strong>Railway Status:</strong><br/>
                            - Models API returned empty list<br/>
                            - Using fallback option above<br/>
                            {loadLLMModels && (
                              <Button 
                                type="button"
                                variant="outline" 
                                size="sm" 
                                className="mt-2"
                                onClick={() => loadLLMModels(true)}
                              >
                                Refresh from Railway
                              </Button>
                            )}
                          </div>
                        )}
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  {/* Speed vs Detail Selection */}
                  <FormField
                    control={form.control}
                    name="speed_vs_detail"
                    render={({ field }) => (
                      <FormItem className="space-y-3">
                        <FormLabel>Planning Detail Level *</FormLabel>
                        <FormControl>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {speedOptions.map((option) => (
                              <Card 
                                key={option.value}
                                className={`cursor-pointer transition-colors ${
                                  field.value === option.value 
                                    ? 'border-blue-500 bg-blue-50' 
                                    : 'hover:border-gray-300'
                                }`}
                                onClick={() => field.onChange(option.value)}
                              >
                                <CardContent className="p-4">
                                  <div className="flex items-center space-x-2">
                                    <input
                                      id={`speed-${option.value}`}
                                      name="speed_vs_detail"
                                      type="radio"
                                      value={option.value}
                                      checked={field.value === option.value}
                                      onChange={() => field.onChange(option.value)}
                                      disabled={isSubmitting}
                                      className="w-4 h-4"
                                    />
                                    <div className="flex-1">
                                      <div className="font-medium">{option.label}</div>
                                      <div className="text-sm text-gray-600">{option.description}</div>
                                      <Badge variant="outline" className="mt-1">
                                        {option.duration}
                                      </Badge>
                                    </div>
                                  </div>
                                </CardContent>
                              </Card>
                            ))}
                          </div>
                        </FormControl>
                        <FormDescription>
                          Choose between comprehensive planning or quick results
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                </TabsContent>

                <TabsContent value="examples" className="space-y-4">
                  <div className="text-sm text-gray-600 mb-4">
                    Click on any example to use it as a starting point for your plan:
                  </div>
                  
                  <div className="grid gap-4 max-h-96 overflow-y-auto">
                    {promptExamples.map((example) => (
                      <Card 
                        key={example.uuid}
                        className={`cursor-pointer transition-colors hover:border-blue-300 ${
                          selectedExample === example.uuid ? 'border-blue-500 bg-blue-50' : ''
                        }`}
                        onClick={() => handleExampleSelect(example)}
                      >
                        <CardContent className="p-4">
                          <div className="font-medium mb-2">{example.title}</div>
                          <div className="text-sm text-gray-600">{example.prompt}</div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </TabsContent>
              </Tabs>

              {/* Submit Button */}
              <div className="flex justify-end space-x-4">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => form.reset()}
                  disabled={isSubmitting}
                >
                  Clear Form
                </Button>
                <Button 
                  type="submit" 
                  disabled={isSubmitting}
                  className="min-w-32"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Creating Plan...
                    </>
                  ) : (
                    'Create Plan'
                  )}
                </Button>
              </div>

            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
};
