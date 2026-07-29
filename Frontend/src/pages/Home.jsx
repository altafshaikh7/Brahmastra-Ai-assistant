import React from 'react';
import AnimatedBlob from '../component/AnimatedBlob';

export default function Home({ blobSettings, setBlobSettings }) {
    return (
        <div className="relative h-screen w-full overflow-hidden">
            {/* Animated Blob Background */}
            <AnimatedBlob blobSettings={blobSettings} setBlobSettings={setBlobSettings} />

            {/* Grid overlay for tech aesthetic */}
            <div className="absolute inset-0 z-0 pointer-events-none opacity-20 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:40px_40px]"></div>
        </div>
    );
}