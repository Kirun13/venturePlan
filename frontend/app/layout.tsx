import type {Metadata} from 'next';import './globals.css';
export const metadata:Metadata={title:'VenturePlan | Multi-Agent Business Planning',description:'Multi-agent business plan workspace'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>}
