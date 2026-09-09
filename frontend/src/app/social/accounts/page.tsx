import { Metadata } from "next";
import { SocialAccountsView } from "@/components/social";

export const metadata: Metadata = {
  title: "Social Accounts | SocialOS",
  description: "Manage connected social media channels and OAuth authorizations for your brand.",
};

export default function SocialAccountsPage() {
  return <SocialAccountsView />;
}
