'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Image as ImageIcon, Upload, Save, Search, AlertCircle, CheckCircle, X, RotateCw, ZoomIn, ArrowLeft } from 'lucide-react';
import Cropper from 'react-easy-crop';
import getCroppedImg from '@/lib/image-cropper';
import { useAuth } from '@/contexts/AuthContext';
import Link from 'next/link';

const API_BASE_URL = 'http://localhost:8000/api';

interface ImageItem {
  key: string;
  value: string; // The image path
  isList?: boolean; // If it came from a list
}

export default function AdminImagesPage() {
  const { token, logout } = useAuth();
  const [data, setData] = useState<any>(null);
  const [images, setImages] = useState<ImageItem[]>([]);
  const [filteredImages, setFilteredImages] = useState<ImageItem[]>([]);
  const [selectedImage, setSelectedImage] = useState<ImageItem | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

  // Cropper state
  const [crop, setCrop] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [croppedAreaPixels, setCroppedAreaPixels] = useState<any>(null);
  const [aspectRatio, setAspectRatio] = useState<number | undefined>(undefined);

  useEffect(() => {
    if (token) {
        fetchData();
    }
  }, [token]);

  useEffect(() => {
    if (searchQuery) {
      const lower = searchQuery.toLowerCase();
      setFilteredImages(images.filter(img => 
        img.key.toLowerCase().includes(lower) || 
        img.value.toLowerCase().includes(lower)
      ));
    } else {
      setFilteredImages(images);
    }
  }, [searchQuery, images]);

  const fetchData = async () => {
    try {
      setIsLoading(true);
      const res = await fetch(`${API_BASE_URL}/admin/website-info`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (res.status === 401) {
        logout();
        throw new Error('Session expired. Please login again.');
      }
      
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`Failed to fetch data: ${res.status} ${res.statusText} - ${text}`);
      }
      const jsonData = await res.json();
      setData(jsonData);
      
      const foundImages: ImageItem[] = [];
      traverse(jsonData, '', foundImages);
      setImages(foundImages);
      setFilteredImages(foundImages);
    } catch (error: any) {
      console.error(error);
      setMessage({ type: 'error', text: error.message || 'Failed to load website info' });
    } finally {
      setIsLoading(false);
    }
  };

  const traverse = (obj: any, path: string, list: ImageItem[]) => {
    if (!obj) return;
    
    if (typeof obj === 'string') {
      // Heuristic: check if string looks like an image path
      // Relaxed check: starts with /images/ OR contains image extension
      if (obj.startsWith('/images/') || obj.match(/\.(jpg|jpeg|png|webp|gif|svg)$/i)) {
        list.push({ key: path, value: obj });
      }
    } else if (Array.isArray(obj)) {
      obj.forEach((item, index) => {
        traverse(item, `${path ? path + '.' : ''}${index}`, list);
      });
    } else if (typeof obj === 'object') {
      Object.keys(obj).forEach(key => {
        traverse(obj[key], `${path ? path + '.' : ''}${key}`, list);
      });
    }
  };

  const getRecommendedSize = (key: string): string => {
    const k = key.toLowerCase();
    if (k.includes('hero')) return '1920 x 1080px';
    if (k.includes('about')) return '800 x 600px';
    if (k.includes('facility')) return '800 x 600px';
    if (k.includes('logo')) return 'SVG / 200 x 60px';
    if (k.includes('icon')) return 'SVG / 64 x 64px';
    return 'Auto / Original';
  };

  const getAspectRatioFromSize = (key: string): number | undefined => {
    const sizeStr = getRecommendedSize(key);
    if (!sizeStr || sizeStr.includes('Auto') || sizeStr.includes('SVG')) return undefined;
    const match = sizeStr.match(/(\d+)\s*x\s*(\d+)/);
    if (match) {
      const w = parseInt(match[1]);
      const h = parseInt(match[2]);
      return w / h;
    }
    return undefined;
  };

  const onCropComplete = useCallback((croppedArea: any, croppedAreaPixels: any) => {
    setCroppedAreaPixels(croppedAreaPixels);
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      setPreviewUrl(URL.createObjectURL(file));
      
      // Reset cropper state
      setCrop({ x: 0, y: 0 });
      setZoom(1);
      setRotation(0);
      
      // Set aspect ratio based on recommended size
      if (selectedImage) {
        const aspect = getAspectRatioFromSize(selectedImage.key);
        setAspectRatio(aspect);
      }
    }
  };

  const handleUpdate = async () => {
    if (!selectedImage || !selectedFile) return;

    try {
      setIsUploading(true);
      setMessage(null);

      let fileToUpload = selectedFile;

      if (croppedAreaPixels && previewUrl && !selectedFile.type.includes('svg')) {
        try {
          const croppedBlob = await getCroppedImg(previewUrl, croppedAreaPixels);
          if (croppedBlob) {
            fileToUpload = new File([croppedBlob], selectedFile.name, { type: selectedFile.type });
          }
        } catch (e) {
          console.error('Failed to crop image:', e);
        }
      }

      const formData = new FormData();
      formData.append('file', fileToUpload);
      formData.append('json_path', selectedImage.key);
      formData.append('current_image_path', selectedImage.value);

      const res = await fetch(`${API_BASE_URL}/admin/update-image`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`
        },
        body: formData,
      });

      if (res.status === 401) {
        logout();
        throw new Error('Session expired. Please login again.');
      }

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Update failed');
      }

      const result = await res.json();
      
      setMessage({ type: 'success', text: 'Image updated successfully!' });
      
      // Update local state
      const newPath = result.new_path;
      setSelectedImage({ ...selectedImage, value: newPath });
      setImages(prev => prev.map(img => img.key === selectedImage.key ? { ...img, value: newPath } : img));
      setSelectedFile(null);
      setPreviewUrl(null);
      
      // Optionally refresh all data
      // fetchData(); 

    } catch (error: any) {
      console.error(error);
      setMessage({ type: 'error', text: error.message });
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 pt-32 pb-12">
      <div className="container mx-auto px-4 max-w-7xl h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center gap-4">
            <Link href="/admin" className="p-2 hover:bg-gray-200 rounded-lg transition-colors flex items-center gap-2 text-gray-600 hover:text-gray-900">
              <ArrowLeft size={24} />
            </Link>
            <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
              <ImageIcon className="text-blue-600" size={32} />
              Website Image Manager
            </h1>
          </div>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
            <input
              type="text"
              placeholder="Search keys or paths..."
              className="pl-10 pr-4 py-2.5 rounded-xl bg-white border border-gray-200 text-gray-900 placeholder-gray-400 focus:ring-2 focus:ring-blue-500 outline-none w-72 shadow-sm"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>

        {/* Content */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 flex-1 overflow-hidden flex">
          {/* List Sidebar */}
          <div className="w-1/3 border-r border-gray-100 overflow-y-auto bg-white">
            {isLoading ? (
              <div className="p-8 text-center text-gray-500">Loading...</div>
            ) : (
              <div className="divide-y divide-gray-100">
                {filteredImages.map((item) => (
                  <div
                    key={item.key}
                    onClick={() => {
                        setSelectedImage(item);
                        setSelectedFile(null);
                        setPreviewUrl(null);
                        setMessage(null);
                    }}
                    className={`p-4 cursor-pointer hover:bg-gray-50 transition-colors ${
                      selectedImage?.key === item.key ? 'bg-blue-50 border-l-4 border-blue-600' : 'border-l-4 border-transparent'
                    }`}
                  >
                    <div className="text-xs font-mono text-gray-500 mb-1 break-all">{item.key}</div>
                    <div className="flex items-start justify-between gap-2">
                      <div className="text-sm font-medium text-gray-900 truncate" title={item.value}>
                        {item.value}
                      </div>
                      <span className="shrink-0 text-[10px] font-medium bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded border border-blue-100">
                        {getRecommendedSize(item.key)}
                      </span>
                    </div>
                  </div>
                ))}
                {filteredImages.length === 0 && (
                  <div className="p-8 text-center text-gray-500">
                    <p>No images found</p>
                    <p className="text-xs mt-2">Data Loaded: {data ? 'Yes' : 'No'}</p>
                    {message && <p className="text-xs text-red-500 mt-2">{message.text}</p>}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Detail View */}
          <div className="w-2/3 flex flex-col overflow-y-auto bg-white">
            {selectedImage ? (
              <div className="p-8 max-w-3xl mx-auto w-full space-y-8">
                {/* Header Info */}
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <h2 className="text-xl font-bold text-gray-900">Edit Image</h2>
                    <span className="text-xs font-medium bg-blue-100 text-blue-800 px-3 py-1 rounded-full border border-blue-200">
                      Recommended: {getRecommendedSize(selectedImage.key)}
                    </span>
                  </div>
                  <code className="block bg-gray-100 p-3 rounded-lg text-sm text-gray-700 break-all border border-gray-200">
                    {selectedImage.key}
                  </code>
                </div>

                <div className="grid grid-cols-2 gap-8">
                  {/* Current Image */}
                  <div className="space-y-4">
                    <h3 className="font-semibold text-gray-700 flex items-center gap-2">
                      Current Image
                    </h3>
                    <div className="aspect-square bg-gray-200 rounded-lg overflow-hidden border border-gray-300 flex items-center justify-center relative">
                        {/* We assume images are served from public root, so usually just relative path works if on same domain. 
                            If backend serves static, we might need full URL. 
                            Since this is admin page in Next.js, it can access public folder directly. */}
                      <img 
                        src={`${selectedImage.value}?t=${new Date().getTime()}`} 
                        alt="Current" 
                        className="max-w-full max-h-full object-contain"
                        onError={(e) => {
                            (e.target as HTMLImageElement).src = 'https://placehold.co/400x400?text=Not+Found';
                        }}
                      />
                    </div>
                    <p className="text-xs text-center text-gray-500 break-all">{selectedImage.value}</p>
                  </div>

                  {/* New Image Preview / Cropper */}
                  <div className="space-y-4">
                    <h3 className="font-semibold text-gray-700 flex items-center gap-2">
                      New Image {previewUrl && !selectedFile?.type.includes('svg') && <span className="text-xs font-normal text-gray-500">(Drag to Crop)</span>}
                    </h3>
                    <div className={`relative bg-white rounded-lg overflow-hidden border-2 border-dashed border-gray-300 flex flex-col items-center justify-center group ${previewUrl ? 'h-80 border-solid border-blue-200' : 'aspect-square hover:border-blue-400'}`}>
                      {previewUrl ? (
                        <>
                           {!selectedFile?.type.includes('svg') ? (
                              <div className="absolute inset-0 z-10">
                                <Cropper
                                  image={previewUrl}
                                  crop={crop}
                                  zoom={zoom}
                                  rotation={rotation}
                                  aspect={aspectRatio}
                                  onCropChange={setCrop}
                                  onCropComplete={onCropComplete}
                                  onZoomChange={setZoom}
                                  onRotationChange={setRotation}
                                />
                              </div>
                           ) : (
                            <img 
                              src={previewUrl} 
                              alt="Preview" 
                              className="max-w-full max-h-full object-contain p-4" 
                            />
                           )}
                           
                           {/* Close button to remove selection */}
                           <button 
                              onClick={(e) => {
                                e.stopPropagation();
                                setSelectedFile(null);
                                setPreviewUrl(null);
                              }}
                              className="absolute top-2 right-2 z-20 bg-white/80 p-1 rounded-full text-gray-600 hover:text-red-500 transition-colors shadow-sm"
                           >
                              <X size={20} />
                           </button>
                        </>
                      ) : (
                        <div className="text-center p-4 text-gray-400 group-hover:text-blue-500">
                          <Upload className="mx-auto mb-2" size={32} />
                          <span className="text-sm">Click to upload</span>
                        </div>
                      )}
                      
                      {!previewUrl && (
                        <input 
                          type="file" 
                          accept="image/*" 
                          onChange={handleFileSelect}
                          className="absolute inset-0 opacity-0 cursor-pointer"
                        />
                      )}
                    </div>
                    
                    {/* Crop Controls */}
                    {previewUrl && !selectedFile?.type.includes('svg') && (
                        <div className="space-y-3 bg-white p-3 rounded-lg border border-gray-100 shadow-sm">
                            <div className="flex items-center gap-3">
                                <ZoomIn size={16} className="text-gray-400" />
                                <input
                                  type="range"
                                  value={zoom}
                                  min={1}
                                  max={3}
                                  step={0.1}
                                  aria-labelledby="Zoom"
                                  onChange={(e) => setZoom(Number(e.target.value))}
                                  className="w-full h-1 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                                />
                            </div>
                            <div className="flex items-center gap-3">
                                <RotateCw size={16} className="text-gray-400" />
                                <input
                                  type="range"
                                  value={rotation}
                                  min={0}
                                  max={360}
                                  step={1}
                                  aria-labelledby="Rotation"
                                  onChange={(e) => setRotation(Number(e.target.value))}
                                  className="w-full h-1 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                                />
                            </div>
                            {aspectRatio && (
                                <div className="text-xs text-center text-blue-600 font-medium">
                                    Fixed Aspect Ratio: {getRecommendedSize(selectedImage?.key || '')}
                                </div>
                            )}
                        </div>
                    )}

                    {selectedFile && (
                        <p className="text-xs text-center text-gray-600">
                            {selectedFile.name} ({(selectedFile.size / 1024).toFixed(1)} KB)
                        </p>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div className="pt-6 border-t border-gray-200 flex items-center justify-between">
                  <div className="flex-1">
                      {message && (
                        <div className={`flex items-center gap-2 text-sm ${message.type === 'success' ? 'text-green-600' : 'text-red-600'}`}>
                            {message.type === 'success' ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
                            {message.text}
                        </div>
                      )}
                  </div>
                  <button
                    onClick={handleUpdate}
                    disabled={!selectedFile || isUploading}
                    className={`px-6 py-2.5 rounded-lg font-semibold flex items-center gap-2 transition-all ${
                      !selectedFile || isUploading
                        ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                        : 'bg-blue-600 text-white hover:bg-blue-700 shadow-md hover:shadow-lg'
                    }`}
                  >
                    {isUploading ? (
                        <>Processing...</>
                    ) : (
                        <>
                            <Save size={18} />
                            Update & Replace
                        </>
                    )}
                  </button>
                </div>

              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-gray-400">
                <ImageIcon size={64} className="mb-4 opacity-20" />
                <p>Select an image from the list to edit</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
