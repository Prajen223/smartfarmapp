import type { Metadata } from "next";

export const metadata: Metadata = {
    title: "FarmSaathi Admin Console",
    description: "Agricultural AI Platform Operations & Analytics Dashboard",
};

export default function AdminLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return <div className="antialiased text-gray-900 bg-gray-50 min-h-screen">{children}</div>;
}
