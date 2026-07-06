import { Link, type Href } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import React from 'react';
import { Platform } from 'react-native';

// `href` uses expo-router's Href type so this compiles both with and
// without Metro's generated typed routes (.expo/types): the generated
// union includes ExternalPathString, and the fallback is string-friendly.
export function ExternalLink(
  props: Omit<React.ComponentProps<typeof Link>, 'href'> & { href: Href }
) {
  return (
    <Link
      target="_blank"
      {...props}
      href={props.href}
      onPress={(e) => {
        if (Platform.OS !== 'web') {
          // Prevent the default behavior of linking to the default browser on native.
          e.preventDefault();
          // Open the link in an in-app browser. External links are plain
          // URL strings; route objects never reach this component.
          void WebBrowser.openBrowserAsync(String(props.href));
        }
      }}
    />
  );
}
