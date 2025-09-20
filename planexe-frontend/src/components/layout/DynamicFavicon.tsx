/* eslint-disable react-hooks/exhaustive-deps */
/**
 * Author: Cascade
 * Date: 2025-09-20T16:44:20-04:00
 * PURPOSE: Dynamic favicon component that generates favicons on-the-fly using Canvas API
 * Works with existing static favicon system - replaces favicon at runtime while preserving initial SEO favicon
 * SRP and DRY check: Pass - Single responsibility for runtime dynamic favicon generation
 */

import React, { useEffect, useRef } from 'react';

interface DynamicFaviconProps {
  randomize?: boolean;
  updateInterval?: number; // milliseconds
  gridSize?: number;
  canvasSize?: number;
  backgroundColor?: string;
}

const DynamicFavicon: React.FC<DynamicFaviconProps> = ({ 
  randomize = false,
  updateInterval = 30000,
  gridSize = 3,
  canvasSize = 32,
  backgroundColor = '#FFFFFF'
}) => {
  const faviconRef = useRef<HTMLLinkElement | null>(null);

  const getRandomColor = (): string => {
    return '#' + Math.floor(Math.random() * 16777215).toString(16).padStart(6, '0');
  };

  const generateFaviconDataUrl = (): string => {
    const canvas = document.createElement('canvas');
    canvas.width = canvasSize;
    canvas.height = canvasSize;
    const ctx = canvas.getContext('2d');
    
    if (!ctx) {
      throw new Error('Could not get canvas context');
    }
    
    const squareSize = Math.floor(canvasSize / gridSize);
    
    // Draw background
    ctx.fillStyle = backgroundColor;
    ctx.fillRect(0, 0, canvasSize, canvasSize);
    
    // Draw grid of colored squares
    for (let row = 0; row < gridSize; row++) {
      for (let col = 0; col < gridSize; col++) {
        const color = getRandomColor();
        ctx.fillStyle = color;
        ctx.fillRect(col * squareSize, row * squareSize, squareSize, squareSize);
      }
    }
    
    return canvas.toDataURL('image/png');
  };

  const updateFavicon = () => {
    try {
      const dataURL = generateFaviconDataUrl();
      
      // Find and remove existing dynamic favicon (preserve original static ones)
      if (faviconRef.current && faviconRef.current.parentNode) {
        faviconRef.current.parentNode.removeChild(faviconRef.current);
      }
      
      // Also remove any existing dynamic favicon links
      const existingDynamicFavicons = document.querySelectorAll('link[rel="icon"][data-dynamic="true"]');
      existingDynamicFavicons.forEach(link => {
        if (link.parentNode) {
          link.parentNode.removeChild(link);
        }
      });
      
      // Create new dynamic favicon link
      const link = document.createElement('link');
      link.rel = 'icon';
      link.type = 'image/png';
      link.href = dataURL;
      link.setAttribute('data-dynamic', 'true'); // Mark as dynamic for cleanup
      
      document.head.appendChild(link);
      faviconRef.current = link;
    } catch (error) {
      console.error('Error updating dynamic favicon:', error);
    }
  };

  useEffect(() => {
    updateFavicon();
    
    let interval: NodeJS.Timeout;
    if (randomize) {
      interval = setInterval(updateFavicon, updateInterval);
    }
    
    return () => {
      if (interval) clearInterval(interval);
      
      // Clean up dynamic favicon on unmount
      if (faviconRef.current && faviconRef.current.parentNode) {
        faviconRef.current.parentNode.removeChild(faviconRef.current);
      }
      
      // Remove all dynamic favicons
      const dynamicFavicons = document.querySelectorAll('link[rel="icon"][data-dynamic="true"]');
      dynamicFavicons.forEach(link => {
        if (link.parentNode) {
          link.parentNode.removeChild(link);
        }
      });
    };
  }, [randomize, updateInterval]);

  return null;
};

export default DynamicFavicon;
