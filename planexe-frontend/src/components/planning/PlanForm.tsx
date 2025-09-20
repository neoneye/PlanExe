/**
 * Author: Cascade
 * Date: 2025-09-19T16:59:36-04:00
 * PURPOSE: Main plan creation form component that replicates Gradio interface functionality with LLM model selection and speed settings
 * SRP and DRY check: Pass - Single responsibility for plan form UI, uses existing form validation schemas
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

interface PlanFormProps {
  onSubmit: (data: CreatePlanRequest) => Promise<void>;
  isSubmitting?: boolean;
  llmModels?: LLMModel[];
  promptExamples?: PromptExample[];
  className?: string;
}

export const PlanForm: React.FC<PlanFormProps> = ({
  onSubmit,
  isSubmitting = false,
  llmModels = [],
  promptExamples = [],
  className = ''
}) => {
  const [selectedModelRequiresKey, setSelectedModelRequiresKey] = useState(false);
  const [selectedExample, setSelectedExample] = useState<string>('');

  const form = useForm<PlanFormData>({
    resolver: zodResolver(PlanFormSchema) as any,
    defaultValues: {
      prompt: '',
      llm_model: '',
      speed_vs_detail: 'ALL_DETAILS_BUT_SLOW',
      openrouter_api_key: '',
      title: '',
      tags: []
    }
  });

  // Watch for LLM model changes to show/hide API key field
  const selectedModel = form.watch('llm_model');

  useEffect(() => {
    if (selectedModel && llmModels.length > 0) {
      const model = llmModels.find(m => m.id === selectedModel);
      setSelectedModelRequiresKey(model?.requires_api_key || false);
    }
  }, [selectedModel, llmModels]);

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
      openrouter_api_key: selectedModelRequiresKey ? data.openrouter_api_key : undefined,
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
      value: 'ALL_DETAILS_BUT_SLOW' as const,
      label: 'All Details (Slow)',
      description: 'Complete analysis with all 50+ tasks (~60 minutes)',
      duration: '45-90 min'
    },
    {
      value: 'FAST_BUT_BASIC' as const,
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
                        <FormLabel>Plan Title (Optional)</FormLabel>
                        <FormControl>
                          <Input 
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
                        <FormLabel>Plan Description *</FormLabel>
                        <FormControl>
                          <Textarea
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
                        <FormLabel>AI Model *</FormLabel>
                        <Select onValueChange={field.onChange} defaultValue={field.value} disabled={isSubmitting}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue placeholder="Select AI model" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {llmModels.map((model) => (
                              <SelectItem key={model.id} value={model.id}>
                                <div className="flex items-center space-x-2">
                                  <span>{model.name}</span>
                                  <Badge variant={model.type === 'paid' ? 'default' : 'secondary'}>
                                    {model.provider}
                                  </Badge>
                                  {model.requiresApiKey && (
                                    <Badge variant="outline" className="text-xs">
                                      API Key
                                    </Badge>
                                  )}
                                </div>
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormDescription>
                          Choose the AI model for plan generation. Paid models generally provide higher quality results.
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  {/* OpenRouter API Key (conditional) */}
                  {selectedModelRequiresKey && (
                    <FormField
                      control={form.control}
                      name="openrouter_api_key"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>OpenRouter API Key *</FormLabel>
                          <FormControl>
                            <Input
                              type="password"
                              placeholder="sk-or-v1-..."
                              {...field}
                              disabled={isSubmitting}
                            />
                          </FormControl>
                          <FormDescription>
                            Your OpenRouter API key is required for paid models. Get one at{' '}
                            <a 
                              href="https://openrouter.ai/" 
                              target="_blank" 
                              rel="noopener noreferrer"
                              className="text-blue-600 hover:underline"
                            >
                              openrouter.ai
                            </a>
                          </FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  )}

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
                          <div className="text-sm text-gray-600 mb-3">{example.prompt}</div>
                          <div className="flex flex-wrap gap-1">
                            {example.tags?.map((tag) => (
                              <Badge key={tag} variant="outline" className="text-xs">
                                {tag}
                              </Badge>
                            ))}
                          </div>
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
                  {isSubmitting ? 'Creating Plan...' : 'Create Plan'}
                </Button>
              </div>

            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
};
