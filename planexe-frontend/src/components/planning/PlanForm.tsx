/**
 * Author: ChatGPT (gpt-5-codex)
 * Date: 2025-10-15
 * PURPOSE: Compact plan creation workflow that connects FastAPI-backed model selection, prompt examples, and submission flow into the landing experience.
 * SRP and DRY check: Pass - component is responsible only for plan creation inputs, reusing shared schemas and API types.
 */

'use client';

import React, { useState, useEffect } from 'react';
import { useForm, ControllerRenderProps } from 'react-hook-form';
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
    <div className={`space-y-4 ${className}`}>
      <Card>
        <CardHeader className="space-y-1 pb-3">
          <CardTitle className="text-base font-semibold text-slate-800">Create new plan</CardTitle>
          <CardDescription className="text-xs text-slate-500">
            Describe your project or idea and let AI assemble the execution pipeline.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 pt-0">
          <Form {...form}>
            <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
              
              {/* Prompt Examples Tab */}
              <Tabs defaultValue="create" className="w-full">
                <TabsList className="grid w-full grid-cols-2 gap-1">
                  <TabsTrigger value="create" className="text-sm">Create</TabsTrigger>
                  <TabsTrigger value="examples" className="text-sm">Examples</TabsTrigger>
                </TabsList>

                <TabsContent value="create" className="space-y-4">
                  
                  {/* Plan Title */}
                  <FormField
                    control={form.control}
                    name="title"
                    render={({ field }: { field: ControllerRenderProps<PlanFormData, 'title'> }) => (
                      <FormItem>
                        <FormLabel htmlFor="plan-title" className="text-sm text-slate-700">Plan title (optional)</FormLabel>
                        <FormControl>
                          <Input
                            id="plan-title"
                            placeholder="e.g. Website Redesign Project"
                            {...field}
                            disabled={isSubmitting}
                          />
                        </FormControl>
                        <FormDescription className="text-xs text-slate-500">
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
                    render={({ field }: { field: ControllerRenderProps<PlanFormData, 'prompt'> }) => (
                      <FormItem>
                        <FormLabel htmlFor="plan-prompt" className="text-sm text-slate-700">Plan description *</FormLabel>
                        <FormControl>
                          <Textarea
                            id="plan-prompt"
                            placeholder="Describe your project, goal, or idea in detail. The more context you provide, the better the plan will be..."
                            className="min-h-[100px]"
                            {...field}
                            disabled={isSubmitting}
                          />
                        </FormControl>
                        <FormDescription className="text-xs text-slate-500">
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
                    render={({ field }: { field: ControllerRenderProps<PlanFormData, 'llm_model'> }) => (
                      <FormItem>
                        <FormLabel htmlFor="llm-model-select" className="text-sm text-slate-700">AI model *</FormLabel>
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
                    render={({ field }: { field: ControllerRenderProps<PlanFormData, 'speed_vs_detail'> }) => (
                      <FormItem className="space-y-3">
                        <FormLabel className="text-sm text-slate-700">Speed vs detail *</FormLabel>
                        <FormControl>
                          <div className="grid gap-3 md:grid-cols-2">
                            {speedOptions.map((option) => (
                              <button
                                key={option.value}
                                type="button"
                                className={`flex h-full w-full flex-col rounded-md border border-slate-200 p-3 text-left transition ${
                                  field.value === option.value
                                    ? 'border-indigo-500 bg-indigo-50'
                                    : 'hover:border-indigo-200'
                                }`}
                                onClick={() => field.onChange(option.value)}
                              >
                                <div className="flex items-start gap-3">
                                  <input
                                    id={`speed-${option.value}`}
                                    name="speed_vs_detail"
                                    type="radio"
                                    value={option.value}
                                    checked={field.value === option.value}
                                    onChange={() => field.onChange(option.value)}
                                    disabled={isSubmitting}
                                    className="mt-1 h-4 w-4"
                                  />
                                  <div className="flex-1 space-y-1">
                                    <div className="text-sm font-semibold text-slate-800">{option.label}</div>
                                    <div className="text-xs text-slate-600">{option.description}</div>
                                    <span className="inline-flex rounded bg-white px-2 py-0.5 text-xs font-medium text-indigo-600 shadow-sm">
                                      {option.duration}
                                    </span>
                                  </div>
                                </div>
                              </button>
                            ))}
                          </div>
                        </FormControl>
                        <FormDescription className="text-xs text-slate-500">
                          Choose between comprehensive planning or quick results
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                </TabsContent>

                <TabsContent value="examples" className="space-y-3">
                  <div className="text-xs text-slate-500">
                    Click any example to seed the form. You can still edit before submitting.
                  </div>

                  {promptExamples.length === 0 ? (
                    <Card className="border-dashed">
                      <CardContent className="py-4 text-center text-sm text-slate-500">
                        No saved prompts yet. Provide your own context above.
                      </CardContent>
                    </Card>
                  ) : (
                    <div className="grid max-h-80 gap-3 overflow-y-auto">
                      {promptExamples.map((example) => (
                        <button
                          key={example.uuid}
                          type="button"
                          className={`flex flex-col items-start gap-2 rounded-md border border-slate-200 p-3 text-left transition ${
                            selectedExample === example.uuid
                              ? 'border-indigo-500 bg-indigo-50'
                              : 'hover:border-indigo-200'
                          }`}
                          onClick={() => handleExampleSelect(example)}
                        >
                          <span className="text-sm font-semibold text-slate-800">{example.title}</span>
                          <span className="text-xs text-slate-600 line-clamp-3">{example.prompt}</span>
                          <Badge variant="secondary" className="mt-1 text-xs">Use this prompt</Badge>
                        </button>
                      ))}
                    </div>
                  )}
                </TabsContent>
              </Tabs>

              {/* Submit Button */}
              <div className="flex flex-col items-start gap-3 border-t border-slate-200 pt-4 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-xs text-slate-500">Plans open in the Workspace automatically for live monitoring.</p>
                <div className="flex w-full items-center justify-end gap-2 sm:w-auto">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => form.reset()}
                    disabled={isSubmitting}
                    className="text-sm"
                  >
                    Clear
                  </Button>
                  <Button
                    type="submit"
                    disabled={isSubmitting}
                    className="min-w-32 text-sm"
                  >
                    {isSubmitting ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Creating...
                      </>
                    ) : (
                      'Create plan'
                    )}
                  </Button>
                </div>
              </div>

            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
};
