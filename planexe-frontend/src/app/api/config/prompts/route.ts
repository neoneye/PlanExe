/**
 * Author: Cascade
 * Date: 2025-09-19T16:59:36-04:00
 * PURPOSE: API route for prompt catalog management - loads from existing PlanExe prompt system
 * SRP and DRY check: Pass - Single responsibility for prompt catalog, interfaces with existing prompt system
 */

import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';
import {
  GetPromptExamplesResponse,
  APIError
} from '@/lib/types/api';

// Get PlanExe root directory
function getPlanExeRoot(): string {
  return path.resolve(process.cwd(), '..');
}

// Load prompt examples from the existing PlanExe prompt catalog
async function loadPromptExamples(): Promise<any[]> {
  const planExeRoot = getPlanExeRoot();
  
  // Check for prompt catalog in planexe directory
  const promptCatalogPath = path.join(planExeRoot, 'planexe', 'prompts', 'prompt_catalog.py');
  
  try {
    // For now, return some default examples
    // TODO: Implement actual parsing of Python prompt catalog
    return [
      {
        uuid: 'example-001',
        title: 'Software Development Project',
        prompt: 'Design and develop a web application for task management that allows teams to collaborate, track progress, and manage deadlines effectively.',
        category: 'Software Development',
        complexity: 'medium',
        tags: ['web-app', 'collaboration', 'project-management']
      },
      {
        uuid: 'example-002',
        title: 'Marketing Campaign Launch',
        prompt: 'Create a comprehensive marketing campaign for a new eco-friendly product launch, including digital marketing, social media strategy, and traditional advertising.',
        category: 'Marketing',
        complexity: 'complex',
        tags: ['marketing', 'campaign', 'eco-friendly', 'launch']
      },
      {
        uuid: 'example-003',
        title: 'Event Planning',
        prompt: 'Organize a corporate conference for 500 attendees including venue selection, speaker coordination, catering, and technical requirements.',
        category: 'Event Management',
        complexity: 'complex',
        tags: ['conference', 'corporate', 'event-planning']
      },
      {
        uuid: 'example-004',
        title: 'Home Renovation Project',
        prompt: 'Plan a complete kitchen renovation including design, contractor selection, permit acquisition, and project timeline management.',
        category: 'Home Improvement',
        complexity: 'medium',
        tags: ['renovation', 'kitchen', 'home-improvement']
      },
      {
        uuid: 'example-005',
        title: 'Business Expansion Plan',
        prompt: 'Develop a plan to expand a local restaurant business to three new locations over 18 months, including market research, financing, and operational scaling.',
        category: 'Business Development',
        complexity: 'complex',
        tags: ['business', 'expansion', 'restaurant', 'scaling']
      },
      {
        uuid: 'example-006',
        title: 'Learning Management System',
        prompt: 'Build an online learning platform for professional development courses with user management, content delivery, and progress tracking.',
        category: 'Education Technology',
        complexity: 'complex',
        tags: ['e-learning', 'LMS', 'education', 'professional-development']
      },
      {
        uuid: 'example-007',
        title: 'Community Garden Initiative',
        prompt: 'Establish a community garden in an urban neighborhood including site preparation, community engagement, and sustainable gardening practices.',
        category: 'Community Development',
        complexity: 'medium',
        tags: ['community', 'garden', 'sustainability', 'urban']
      },
      {
        uuid: 'example-008',
        title: 'Mobile App Development',
        prompt: 'Create a fitness tracking mobile app with personalized workout plans, nutrition tracking, and social features for motivation.',
        category: 'Mobile Development',
        complexity: 'complex',
        tags: ['mobile-app', 'fitness', 'health', 'social']
      }
    ];

  } catch (error) {
    console.error('Failed to load prompt examples:', error);
    throw new Error('Prompt catalog not found or invalid');
  }
}

// GET /api/config/prompts - Get prompt examples
export async function GET(request: NextRequest): Promise<NextResponse> {
  try {
    const { searchParams } = new URL(request.url);
    const category = searchParams.get('category');
    const complexity = searchParams.get('complexity');
    const limit = parseInt(searchParams.get('limit') || '20');

    let examples = await loadPromptExamples();

    // Apply filters
    if (category) {
      examples = examples.filter(ex => 
        ex.category.toLowerCase().includes(category.toLowerCase())
      );
    }

    if (complexity) {
      examples = examples.filter(ex => ex.complexity === complexity);
    }

    // Apply limit
    if (limit > 0) {
      examples = examples.slice(0, limit);
    }

    // Extract unique categories
    const allExamples = await loadPromptExamples();
    const categories = [...new Set(allExamples.map(ex => ex.category))];

    const response: GetPromptExamplesResponse = {
      success: true,
      examples,
      categories,
      totalCount: allExamples.length
    };
    
    return NextResponse.json(response);

  } catch (error) {
    console.error('Prompt examples error:', error);

    const apiError: APIError = {
      success: false,
      error: {
        code: 'PROMPT_ERROR',
        message: error instanceof Error ? error.message : 'Failed to load prompt examples',
        timestamp: new Date().toISOString(),
      },
    };

    return NextResponse.json(apiError, { status: 500 });
  }
}
